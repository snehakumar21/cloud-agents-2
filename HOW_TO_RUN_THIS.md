# How to Run the Cloud Resource Allocation Project (Mac)

This guide is written for someone new to programming and cloud tools. Follow the steps in order. You can run the project in **Simulation** mode without an AWS account. To see real AWS resources, complete the optional AWS setup and choose **AWS Read-Only** in the dashboard.

> **Safety:** AWS mode only reads EC2 inventory and CPU metrics. It does not start, stop, resize, or move AWS resources. AWS can still contain private account information, so do not share screenshots or expose the backend publicly without first securing it.

## What you will set up

The project runs as two local programs:

- The **backend** is the service that runs the project logic and talks to AWS (if configured).
- The **frontend** is the website/dashboard you open in your browser.

You will keep both programs running in two Terminal windows while using the dashboard.

## Part 1: Install the tools (once)

### 1. Open Terminal

On your Mac, open **Finder → Applications → Utilities → Terminal**. You can also press Command-Space, type `Terminal`, and press Return.

A window with a text prompt will appear. You will type or paste commands into this window and press Return to run them. A command may print text and then show another prompt; that usually means it finished. When a command is still running, leave that window open.

### 2. Install Apple's command-line tools

Copy this command into Terminal and press Return:

```bash
xcode-select --install
```

If macOS shows an installation window, choose **Install** and wait for it to finish. If it says the tools are already installed, continue.

### 3. Install Python

This project needs Python 3.10 or newer. Check whether it is available:

```bash
python3 --version
```

If the output says `Python 3.10` or a higher version, continue. If Terminal says the command cannot be found or shows an older version, install a current Python 3 release from [python.org/downloads/macos](https://www.python.org/downloads/macos/). Open the downloaded installer and follow its instructions, then close and reopen Terminal and run `python3 --version` again.

### 4. Install Node.js

Node.js runs the dashboard development server. Install the current **LTS** release from [nodejs.org](https://nodejs.org/): download the macOS installer, open it, and follow the installer steps.

Close and reopen Terminal, then check both Node.js and npm:

```bash
node --version
npm --version
```

Both commands should print version numbers. If either is not found, restart Terminal and try again. If it is still missing, rerun the Node.js installer.

## Part 2: Find the project folder

You need the project folder on your Mac. If the project was provided as a ZIP file, double-click it in Finder to extract it. Find the extracted folder named `cloud-agents-2`.

In Terminal, move into the project folder. The easiest way is to type `cd ` (with a space after `cd`), drag the `cloud-agents-2` folder from Finder into the Terminal window, then press Return. For example, the command might look like this (your location may differ):

```bash
cd /Users/yourname/Projects/cloud-agents-2
```

Check that you are in the right folder:

```bash
ls
```

You should see names including `README.md`, `HOW_TO_RUN_THIS.md`, `backend`, and `frontend`. If you do not, repeat the `cd` step using the actual project folder.

## Part 3: Start the backend

### 1. Open a backend Terminal window

In Terminal, enter the backend folder:

```bash
cd backend
```

### 2. Create a private Python environment for this project

This keeps the project's Python packages separate from the rest of your Mac:

```bash
python3 -m venv .venv
```

This normally completes without much output. You only need to create this environment once. If the `.venv` folder already exists, you can continue.

### 3. Turn on the environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` at the beginning of the Terminal prompt. If you open a new backend Terminal window later, run this activation command again.

### 4. Install the backend packages

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Wait for the installation to finish and for the Terminal prompt to return. An internet connection is needed for this step. If you see an error, check your internet connection and try the two commands again.

### 5. Start the backend service

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this Terminal window open. The backend is running while the window shows server messages instead of a normal prompt. Do not type other commands into this window. If macOS asks whether Python can accept network connections, allow local connections if prompted.

You can check the backend in a browser by opening [http://127.0.0.1:8000](http://127.0.0.1:8000). The page should show a short message about the service. The interactive API page is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Part 4: Start the dashboard

### 1. Open a second Terminal window

Keep the backend running. Open another Terminal window using **Shell → New Window** (or press Command-N).

Go to the project folder again. Type `cd ` and a space, drag the `cloud-agents-2` folder from Finder into Terminal, and press Return. Then enter the frontend folder:

```bash
cd frontend
```

If Terminal says there is no `frontend` folder, you are not at the project root. Use `cd ..` once and check with `ls`.

### 2. Install the dashboard packages

```bash
npm install
```

This can take a few minutes and needs an internet connection. Wait for the prompt to return. If this command reports a package installation error, check your connection and try it once more.

### 3. Start the dashboard

```bash
npm run dev
```

Leave this Terminal window open too. It should display a local address, usually `http://localhost:5173`.

### 4. Open the dashboard

In your browser, visit [http://localhost:5173](http://localhost:5173). You should see **Cloud Resource Allocation**.

The dashboard needs both Terminal windows to remain open: one for the backend and one for the frontend. Closing a window or pressing Control-C in it stops that part of the project.

## Part 5: Try the simulation (no AWS account required)

The project opens in **Simulation** mode. This mode uses sample servers, jobs, metrics, and made-up costs stored locally in the backend; these are not AWS resources and do not cost AWS money.

- Click **Normal Load**, **Traffic Spike**, or **Underutilization** to select a sample situation.
- Click **Run One Cycle** to have the agents examine the situation and make simulated decisions.
- Click **Start Simulation** to run cycles automatically. Click **Stop** to stop them.
- Click **Reset** to restart the selected sample situation.
- Look at the agent panels and decision log to see what the agents observed and decided.

## Part 6: Optional — connect AWS in read-only mode

Skip this section if you only want to run the simulation. To use AWS mode, you need an AWS account and permission to view EC2 and CloudWatch in that account. Ask the account owner or administrator for help if you do not have those permissions. AWS may incur costs from resources that already exist in the account; this project does not create those resources.

### 1. Pick a safe AWS account and region

Use a development/test AWS account if possible, not a production account. Choose the region where your test EC2 instances are located, for example `us-east-1` (Northern Virginia). An AWS region is the geographic area containing the resources you want to view.

### 2. Install the AWS CLI

The AWS CLI is a command-line tool for signing in and checking which AWS account your Mac is using. Install it using the official AWS guide: [Installing or updating the AWS CLI on macOS](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

After installation, close and reopen Terminal, then run:

```bash
aws --version
```

A version number should appear. If Terminal cannot find `aws`, follow the AWS installation guide again and reopen Terminal.

### 3. Ask the AWS administrator for read-only access

The AWS identity used by the backend needs permission to:

- list EC2 instance information (`ec2:DescribeInstances`)
- read EC2 CPU measurements (`cloudwatch:GetMetricStatistics`)

The account administrator can create an IAM policy for you. The policy content is below; they can attach it to your AWS user or role according to the organization's rules. This policy only reads data and does not give permission to start or stop instances.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ec2:DescribeInstances"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["cloudwatch:GetMetricStatistics"],
      "Resource": "*"
    }
  ]
}
```

Do not ask for administrator access just to run this project. If you do not control the AWS account, ask its owner to set up the limited read-only access instead.

### 4. Sign in to AWS from Terminal

For a school or organization account using AWS IAM Identity Center/SSO, follow the organization's sign-in instructions. Commonly, the command is:

```bash
aws configure sso
```

Follow the prompts. Choose the profile and account/role that the administrator gave you. After sign-in, verify which identity is active:

```bash
aws sts get-caller-identity
```

It should print your AWS account and identity information. If it says you are not logged in or do not have permission, ask the AWS administrator for help. Do not paste access keys or secret keys into this guide, the project files, or the browser.

If your organization uses a named AWS profile, remember its profile name. The default profile requires no extra setting. For another profile, you will set `AWS_PROFILE` in the backend Terminal in the next step.

### 5. Configure AWS in the backend Terminal

Stop the backend first if it is already running: click its Terminal window and press **Control-C**. Now, in that same backend Terminal, go to the `backend` directory if needed and activate the environment:

```bash
cd /path/to/cloud-agents-2/backend
source .venv/bin/activate
```

Replace `/path/to/cloud-agents-2/backend` with your actual folder location. One simple way to get the path is to type `cd ` and a space, drag the project's `backend` folder from Finder into Terminal, then press Return. If the prompt already starts with `(.venv)`, the environment is active; running the activation command again is okay.

Set the AWS region. Replace `us-east-1` with your chosen region:

```bash
export AWS_REGION=us-east-1
```

If you were given a named profile other than the default, also set it (replace `student` with the profile name you were given):

```bash
export AWS_PROFILE=student
```

These settings apply to this Terminal window. They need to be set again whenever you open a new backend Terminal window.

### 6. (Recommended) Limit which instances appear

By default, the dashboard can list every EC2 instance that your read-only credentials can see in the chosen region. To show only instances marked for this demo, ask the administrator to add a tag to the test instances. For example, use tag key `CloudAllocator` and value `demo`.

Then, in the backend Terminal, set these values before starting the backend:

```bash
export AWS_MANAGED_TAG_KEY=CloudAllocator
export AWS_MANAGED_TAG_VALUE=demo
```

The key and value must exactly match the tag on the AWS instances. If you do not set both values, the tag filter is not used.

### 7. Restart the backend and open AWS mode

In the backend Terminal, start the backend again:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep it running. In the browser dashboard, click **AWS Read-Only**. Click **Refresh AWS inventory** to request an up-to-date inventory. The dashboard displays instance ID/name, type, state, region, and CPU measurements when CloudWatch has them.

AWS CPU measurements may take a while to appear for a new instance. The project displays **Unavailable** if AWS has not provided a measurement; this does not mean CPU usage is zero. Standard EC2 metrics do not include memory utilization, so memory usage is not displayed. This version does not calculate AWS prices.

### 8. Troubleshooting AWS mode

- **AWS inventory unavailable:** Make sure the backend Terminal is running, `boto3` was installed from `requirements.txt`, and you set AWS variables in the same Terminal before starting the backend.
- **Credentials/sign-in error:** Run `aws sts get-caller-identity` in a Terminal window where your AWS sign-in is active. For SSO, sign in again using your organization's process (often `aws sso login --profile PROFILE_NAME`). Set `AWS_PROFILE` in the backend Terminal if needed.
- **Access denied:** Ask the account administrator to check the two read permissions in step 3.
- **No instances shown:** Check the region and, if enabled, the tag key and value. Also confirm the credentials can see the instances.
- **CPU unavailable:** Wait and refresh. CloudWatch may not yet have datapoints for a new instance.
- **Address already in use:** A previous backend or frontend may still be running. Find its Terminal window and press Control-C before starting it again.
- **Dashboard cannot connect:** Confirm both backend and frontend Terminal windows are still running, then reload `http://localhost:5173`.

## Stop the project

When you are done, click each Terminal window that is running the project and press **Control-C**. This stops the dashboard server and backend. Your simulated state will reset when the backend restarts. No AWS resource changes are made by this project.

## Start it again another day

1. Open Terminal and go to the project's `backend` folder.
2. Activate the Python environment with `source .venv/bin/activate`.
3. If using AWS, set `AWS_REGION` and any needed `AWS_PROFILE` / tag variables again.
4. Start the backend with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
5. Open a second Terminal, go to the project's `frontend` folder, and run `npm run dev`.
6. Open `http://localhost:5173` in your browser.

You only need to run `python -m pip install -r requirements.txt` and `npm install` again if dependencies were not installed, or the project files/dependencies have changed.
