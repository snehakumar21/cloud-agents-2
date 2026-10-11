"""
Run from the backend folder:   python -m unittest discover -s tests -v
Pure Python, no extra packages needed.
"""
import unittest
from app.state import CloudState
from app.orchestrator import Orchestrator
from app.agents import linear_forecast


def make(key):
    st = CloudState()
    orch = Orchestrator(st)
    orch.load_scenario(key)
    return st, orch


def layout(st):
    return {s.id: (s.powered_on, sorted(j.name for j in s.jobs)) for s in st.servers}


class ScenarioTests(unittest.TestCase):
    def test_same_scenario_same_start(self):
        a, _ = make("spike")
        b, _ = make("spike")
        self.assertEqual(a.to_dict()["history"], b.to_dict()["history"])
        self.assertEqual(layout(a), layout(b))

    def test_same_scenario_same_cycle_results(self):
        a, oa = make("spike")
        b, ob = make("spike")
        for _ in range(4):
            oa.run_cycle(); ob.run_cycle()
        self.assertEqual(layout(a), layout(b))
        self.assertEqual([l["decision"] for l in a.logs], [l["decision"] for l in b.logs])

    def test_normal_no_migration_or_scaling(self):
        st, o = make("normal")
        for _ in range(8):
            o.run_cycle()
            st.assert_invariants()
        decisions = " ".join(l["decision"] for l in st.logs)
        self.assertNotIn("Migrated", decisions)
        self.assertNotIn("Scaled", decisions)
        self.assertNotIn("Consolidated", decisions)
        self.assertEqual(len(st.pending), 0)
        self.assertEqual(st.hourly_cost(), 1.20)

    def test_spike_detects_predicts_migrates_scales(self):
        st, o = make("spike")
        before = st.snapshot()
        r = o.run_cycle()
        logs = [l for l in st.logs if l["cycle"] == 1]
        text = " | ".join(f"{l['agent']}: {l['decision']}" for l in logs)
        self.assertIn("Hotspot detected: srv-1", text)
        self.assertIn("Predicted overload: srv-1", text)
        self.assertIn("Migrated img-resize: srv-1 -> srv-2", text)
        self.assertIn("No safe migration available for srv-1", text)
        self.assertIn("Scaled out: powered on srv-3", text)
        self.assertLess(r["comparison"]["after"]["max_cpu"], before["max_cpu"] - 10)
        self.assertGreater(r["comparison"]["delta"]["hourly_cost"], 0)    # cost goes UP, honestly reported
        o.run_cycle()
        self.assertLess(st.snapshot()["max_cpu"], 70)           # no server above the relief target
        self.assertLess(st.get_server("srv-1").cpu_pct(), 60)   # the hotspot is gone
        st.assert_invariants()

    def test_rejection_reason_mentions_capacity(self):
        st, o = make("spike")
        o.run_cycle()
        warn = [l for l in st.logs if l["decision"].startswith("No safe migration")][0]
        self.assertIn("powered off", warn["explanation"])
        self.assertIn("ml-inference", warn["explanation"])
        self.assertIn("RAM", warn["explanation"])

    def test_underused_consolidates_and_saves(self):
        st, o = make("underused")
        r = o.run_cycle()
        self.assertEqual(st.hourly_cost(), 0.80)
        self.assertFalse(st.get_server("srv-3").powered_on)
        self.assertEqual(st.get_server("srv-3").jobs, [])
        self.assertEqual(sum(len(s.jobs) for s in st.servers), 6)       # no job lost
        self.assertEqual(r["comparison"]["delta"]["hourly_cost"], -0.40)
        self.assertGreater(r["comparison"]["delta"]["avg_cpu"], 0)       # remaining servers run hotter
        st.assert_invariants()

    def test_consolidation_blocked_when_jobs_do_not_fit(self):
        st, o = make("underused")
        # make the other servers heavy so srv-3's jobs cannot fit under the 70% / 75% limits
        from app.models import Job
        st.get_server("srv-1").jobs.append(Job("filler-1", 7.0, 12.0))
        st.get_server("srv-2").jobs.append(Job("filler-2", 7.0, 12.0))
        o.run_cycle()
        self.assertTrue(st.get_server("srv-3").powered_on)
        self.assertTrue(any(l["decision"] == "Consolidation blocked" for l in st.logs))

    def test_no_oscillation_over_many_cycles(self):
        for key in ("normal", "spike", "underused"):
            st, o = make(key)
            power_changes = 0
            moves = {}
            for _ in range(30):
                o.run_cycle()
                st.assert_invariants()
            for l in st.logs:
                if l["decision"].startswith(("Scaled out", "Consolidated")):
                    power_changes += 1
                if l["decision"].startswith("Migrated"):
                    job = l["decision"].split()[1].rstrip(":")
                    moves.setdefault(job, []).append(l["cycle"])
            self.assertLessEqual(power_changes, 1, key)
            for job, cycles in moves.items():
                for a, b in zip(cycles, cycles[1:]):
                    self.assertGreaterEqual(b - a, 3, f"{key}:{job} moved too soon")

    def test_insufficient_history_is_reported(self):
        st, o = make("spike")
        o.run_cycle()    # srv-3 powered on in cycle 1
        o.run_cycle()    # cycle 2: srv-3 has only 1 sample
        f = st.agent_status["prediction"]["data"]["observation"]["forecasts"]["srv-3"]
        self.assertEqual(f["status"], "insufficient_history")
        self.assertNotIn("forecast_cpu", f)

    def test_linear_forecast_math(self):
        forecast, slope = linear_forecast([10, 20, 30, 40, 50])
        self.assertAlmostEqual(slope, 10.0)
        self.assertAlmostEqual(forecast, 70.0)   # 2 cycles ahead of the last point (50 + 2*10)

    def test_never_exceeds_capacity_on_forced_bad_move(self):
        st, _ = make("spike")
        with self.assertRaises(ValueError):
            st.migrate_job("checkout-api", "srv-1", "srv-3")   # srv-3 is powered off
        with self.assertRaises(ValueError):
            st.place_pending  # attribute exists
            from app.models import Job
            st.pending.append(Job("huge", 99.0, 1.0))
            st.place_pending("huge", "srv-2")


if __name__ == "__main__":
    unittest.main()
