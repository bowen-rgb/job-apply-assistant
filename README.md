<div align="center">

# Job Apply Assistant

**A personal workspace for finding jobs, preparing applications and following up.**

English · [简体中文](README.zh-CN.md)

[Get started](#get-started) · [Features](#a-clearer-application-process) · [User guide](USER_GUIDE.md) · [Documentation](docs/README.md)

</div>

![Job Apply Assistant: your next role, one clear workspace](docs/assets/hero.svg)

<p align="center">
  <img alt="Version 8.4" src="https://img.shields.io/badge/version-8.4-2247df?style=flat-square">
  <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/Python-3.11%2B-20342b?style=flat-square">
  <img alt="Windows setup included" src="https://img.shields.io/badge/setup-Windows-20342b?style=flat-square">
  <img alt="Chinese and French interface" src="https://img.shields.io/badge/interface-Chinese_%2F_French-687762?style=flat-square">
</p>

Keep job discovery, CVs, application preparation and follow-up records in one local workspace. Start with a guided manual application, then enable browser assistance when you need it. Your profile and application history are stored on your computer.

**Windows Dashboard:** double-click `start.bat` to open the browser with a hidden backend. `setup_dashboard.bat` creates shortcuts; `stop_dashboard.bat` stops owned workers; `uninstall_dashboard.bat` removes shortcuts while preserving candidate data. [Dashboard guide](docs/DASHBOARD.md).

## A clearer application process

**Graduation internships / research:** open **PFE & research** for direction-based discovery, research-team leads, campus announcements and source evidence. See the [PFE guide](docs/PFE_DISCOVERY.md). Contract duration limits now belong to each candidate profile; blank means unrestricted.

**Platform automation:** open dedicated Chrome from **Pipeline & queue**, check its connection, then start the queue separately. The platform runs its own workers and never falls back to Edge. See [Chrome controls and verification limits](docs/CHROME_AUTOMATION_CONTROL.md).

**QR applications:** upload a recruiter QR image, check the recipient and suggested CV, then start that single application. The old queue stays paused. See [workflow and support limits](docs/QR_APPLICATIONS.md).

| Find the right opportunities | Prepare with context |
| --- | --- |
| Search supported job sites, public ATS boards and custom sources. Combine campaigns and deduplicate repeated vacancies. | Keep multiple CVs, review job fit and optionally generate a tailored French cover letter through your signed-in ChatGPT browser session. |
| **Keep the next step visible** | **Follow the real outcome** |
| A live dashboard and preparation queue show what is running, what is ready and where your input is needed. | Track saved jobs, confirmed submissions, interviews and outcomes. Export review reports as standalone HTML or Excel. |
| **Separate candidate workspaces** | **Choose your language** |
| Give each candidate their own profile, documents, accounts, tasks and history. | Use Chinese or French. Original job titles remain available for verification. |

### From discovery to follow-up

1. **Set up your profile.** Add your CV, preferred roles, locations and availability.
2. **Find and review jobs.** Compare the original listings and confirm AI-reviewed recommendations yourself.
3. **Prepare an application.** Queue a selected job, check its documents and take over when input is needed.
4. **Submit and follow up.** Submission is manual by default. Record successful sending and later recruiter responses.

<details>
<summary><strong>See the real workspace</strong> — fresh profile, compact layout</summary>

This screenshot shows the running application with an empty candidate workspace. Zero counts are real; no sample applications or personal CVs were added for the image.

<img src="docs/assets/dashboard-zh.png" alt="Chinese workspace in its narrow-screen layout, showing an empty profile, next steps and application tracking" width="380">

</details>

## Get started

**Windows · Python 3.11+ · Chrome or Edge**

Clone the project and run the Windows installer:

```powershell
git clone https://github.com/bowen-rgb/job-apply-assistant.git
cd job-apply-assistant
.\run_windows.bat
```

The installer creates an isolated Python environment, installs the runtime and browser components, prepares a local profile and opens **<http://127.0.0.1:8765>**.

For later launches, double-click **`start.bat`**. In the sidebar, choose **Start here** for a guided first application, or **Profile & preferences** to add your details and CV.

| What you want to do | What you need |
| --- | --- |
| Apply manually and keep records | Your profile, CV and a recruiter website. ChatGPT is optional. |
| Review job fit or generate a cover letter | Sign in to ChatGPT in the dedicated browser opened by the launcher. No OpenAI API key is required. |
| Prepare supported application forms | An active CV, complete profile and the dedicated browser connection. Some sites require manual intervention. |

**Windows startup:** The server runs in the background without a console window. Reopening `start.bat` reuses a healthy server. Logs and process details are saved in `data/server-logs/`. Dedicated Chrome remains visible for login and application handoff. Startup errors are shown in the launcher.

**Need help?** Run `doctor.bat`, then check the [user guide](USER_GUIDE.md), [accounts guide](ACCOUNT_SETUP.md) or [installation notes](FIX_V8_2.md).

<details>
<summary>Manual environment setup</summary>

The Windows launchers are the supported starting point. To prepare the Python environment yourself, run these steps separately:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-jobspy.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-scrapling.txt
.\.venv\Scripts\python.exe -m playwright install chromium
if (-not (Test-Path profile.json)) { Copy-Item profile.example.json profile.json }
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Use `start_chrome_debug.bat` when you need browser assistance. Its default local connection is `http://127.0.0.1:9222`. Keep your usual browser profile separate from this dedicated session.

</details>

## Your data and your decisions

- **Local storage.** Profiles, CVs, browser sessions, credentials and job records are excluded from Git. The server accepts local connections only. Saved website passwords use Windows user encryption.
- **Optional external assistance.** ChatGPT features send the selected job, profile or CV text needed for the requested task to your signed-in ChatGPT session. On-demand title translation may send public job titles to MyMemory. Local storage does not mean every feature works offline.
- **Manual sending by default.** Automatic queue start and automatic submission are separate settings. Automatic sending also requires your approval of the prepared CV, letter and combined packet versions. Changes to the documents, listing or saved profile require another review. Approval alone never sends an application: explicitly run preparation again to use approved versions.
- **Submission evidence.** Manual confirmation records an application as sent. The “confirmed by the site” label requires a browser-observed confirmation and an intact local receipt. A recorded send attempt blocks automatic retries after an uncertain result or interruption. A confirmation page is evidence of what the browser observed, not a guarantee of recruiter delivery.
- **Clear handoffs.** Missing information, CAPTCHA, MFA, consent and uncertain send outcomes pause automation. Gmail connection setup is available; automatic verification-code retrieval and password recovery are not implemented.

See [material review and submission evidence](docs/APPLICATION_SAFETY.md) for the workflow and its limits.

Job-site access and results depend on the source. A matching score or an AI recommendation does not establish that a vacancy is still open. Read the original listing and review prepared forms before sending.

## Documentation

| Start here | Explore further |
| --- | --- |
| [User guide · French / Chinese](USER_GUIDE.md) | [Architecture and module boundaries](ARCHITECTURE.md) |
| [Candidate profiles, website accounts and Gmail](ACCOUNT_SETUP.md) | [Dashboard design and metric definitions](DASHBOARD_DESIGN.md) |
| [Research and application workflow](RESEARCH_WORKFLOW.md) | [Interface design](DESIGN.md) |
| [Reusable frontend design Skill](skills/practical-ui-design/SKILL.md) | [UI reference decisions](docs/design/REFERENCE_DECISIONS.md) |
| [V8.4 changes](CHANGELOG_V8_4.md) | [Earlier feature and release notes](docs/archive/README-before-refresh.md) |

## Development

The application uses **FastAPI, SQLite and a plain JavaScript interface**, with Playwright, Scrapling and optional JobSpy integrations. There is no separate npm build step.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For bugs and feature requests, [open an issue](https://github.com/bowen-rgb/job-apply-assistant/issues). Include the steps to reproduce and relevant diagnostics; remove personal details and credentials first.

---

[Open-source references](OPEN_SOURCE_REFERENCES.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [README design references](docs/README_DESIGN.md)


完整求职工具：在“求职进度与队列”中展开，可使用逐岗 CV、面试／模拟面试、学习计划、扩展来源、LinkedIn 帖子、多模型、Notion、邮件草稿和批量数据工具。操作示例与可选连接配置见 [docs/CAREER_TOOLS.md](docs/CAREER_TOOLS.md)。
