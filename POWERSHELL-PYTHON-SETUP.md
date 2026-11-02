# PowerShell and Python setup notes

This note records the Python and PowerShell commands discussed while setting
up this project. Commands shown under **Confirmed in the conversation** were
included in terminal output you shared. Commands under **Suggested** were
recommended during troubleshooting; it is not known whether you ran them.

## Confirmed in the conversation

### Try to create a standard virtual environment

```powershell
python -m venv venv
```

This asks the `python` command to create a virtual environment in the `venv`
folder. It failed with “Python was not found,” so this attempt did not create
the environment. Windows could not find a Python executable under that
command.

### Install uv

VS Code ran:

```powershell
powershell -ExecutionPolicy Bypass -c 'irm https://astral.sh/uv/install.ps1 | iex'
```

- `powershell` starts a PowerShell process.
- `-ExecutionPolicy Bypass` allows scripts in that process to run, without
  permanently changing the user's execution policy.
- `irm` is an alias for `Invoke-RestMethod`; it downloads the installer script
  from the URL.
- `iex` is an alias for `Invoke-Expression`; it runs the downloaded script.

The output showed uv installed under
`C:\Users\arun_\.local\bin`. Piping a downloaded script directly into
`Invoke-Expression` executes it immediately, so only do this for a source you
trust.

### Install uv-managed Python

VS Code then ran:

```powershell
C:\Users\arun_\.local\bin\uv.exe python install
```

The output reported that Python 3.15.2 was installed. This installs a
uv-managed Python, but does not necessarily make `python` available as a
command in every terminal.

### Try to activate a virtual environment

```powershell
.\venv\Scripts\activate.ps1
```

This attempted to run the activation script from the `venv` folder in the
current project directory. PowerShell blocked it because of the execution
policy. That is a restriction on running the script, not proof that the
environment itself is broken.

## Suggested commands

These were offered as possible next steps; whether they have been run is
unknown.

### Check for the Python launcher

```powershell
py --version
py -m venv venv
```

`py` is the Windows Python launcher. If installed and configured, it can find
Python even when the `python` command is unavailable.

### Use uv with Python 3.12

The following uses uv by its full path, so it does not depend on `uv` being
available on `PATH`:

```powershell
$uv = "$HOME\.local\bin\uv.exe"
& $uv python install 3.12
& $uv venv --python 3.12 .venv
```

- `$HOME` is the current user's home directory.
- `$uv` stores the path to `uv.exe`.
- PowerShell's `&` call operator runs the executable stored in `$uv`.
- The first uv command installs Python 3.12 under uv's management.
- The second creates a virtual environment in `.venv` using Python 3.12.

After adding `C:\Users\arun_\.local\bin` to the user `Path` and opening a new
terminal, the shorter form is:

```powershell
uv --version
uv python install 3.12
uv venv --python 3.12 .venv
```

An alternative temporary `Path` change for the current PowerShell window is:

```powershell
$env:Path = "$HOME\.local\bin;$env:Path"
```

The temporary change disappears when that terminal closes. The user `Path`
shown during setup already included `C:\Users\arun_\.local\bin`, so after
restarting PowerShell or VS Code, `uv` should be available without this
temporary command.

If the project has a `requirements.txt`, uv can install its packages into the
`.venv` environment without activating it:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

### Activate the environment

PowerShell activation was suggested with a temporary policy change:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

`Process` limits the policy change to the current PowerShell process; closing
that terminal discards the change. If the environment is `.venv`, use its
activation script instead:

```powershell
.\.venv\Scripts\Activate.ps1
```

Another suggested option was to allow locally created scripts for the current
Windows user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

This persists for that user and is not limited to VS Code. `RemoteSigned`
allows local scripts and generally requires downloaded scripts to be signed.
An organization-managed policy can override it. To inspect the policy scopes:

```powershell
Get-ExecutionPolicy -List
```

### Check or use a Conda environment

If choosing Anaconda instead of uv for this project's Python environment:

```powershell
conda --version
conda create -n ai-event-platform python=3.12
conda activate ai-event-platform
python --version
```

If the project has a `requirements.txt`, install those dependencies after
activating the environment:

```powershell
pip install -r requirements.txt
```

Use either Conda or `.venv` for the project's environment; there is usually no
need to nest one environment inside the other.

## Keep the environment folder consistent

The commands discussed used both `venv` and `.venv`. These are different
folders. Choose the one that exists in the project and use it consistently
for activation and VS Code's **Python: Select Interpreter**. For example, if
using `.venv`, the interpreter is `.venv\Scripts\python.exe`.
