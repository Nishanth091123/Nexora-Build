"""Push Nexora Build to GitHub – safely. Your .env (keys) is NEVER uploaded.

    backend\\.venv\\Scripts\\python.exe scripts\\github_push.py  [message]

Before pushing it checks: .env is ignored by git, and no key value from .env appears in any file
that would be uploaded. If anything looks like a key, it stops and shows the file.
Repository: https://github.com/Nishanth091123/Nexora-Build  (create it EMPTY on github.com first:
no README, no .gitignore, no licence). The first push opens a GitHub login window.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "https://github.com/Nishanth091123/Nexora-Build.git"
# generic key shapes, in case a key is pasted somewhere that is not in .env
PATTERNS = [r"AIza[0-9A-Za-z_\-]{30,}", r"gsk_[0-9A-Za-z]{30,}", r"sk-or-v1-[0-9a-f]{40,}", r"hf_[0-9A-Za-z]{30,}",
            r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]{6,}@", r"ghp_[0-9A-Za-z]{30,}"]


def git(*args, check=True, capture=False):
    r = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=capture)
    if check and r.returncode != 0:
        if capture:
            print(r.stdout, r.stderr)
        sys.exit(f"[FAIL] git {' '.join(args)}")
    return r


def env_values() -> list[str]:
    p = ROOT / ".env"
    vals = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if re.search(r"KEY|SECRET|TOKEN|PASSWORD|DATABASE_URL|ACCOUNT_ID", k.upper()) and len(v) >= 8:
                    vals.append(v)
    return vals


def main() -> int:
    msg = " ".join(sys.argv[1:]) or "Nexora Build update"
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        sys.exit("[FAIL] Git is not installed. Install it from https://git-scm.com/download/win and run again.")
    if not (ROOT / ".git").exists():
        git("init", "-b", "main")
        print("[OK] New git repository")
    if not git("config", "user.name", check=False, capture=True).stdout.strip():
        git("config", "user.name", "Nishanth S")
    if not git("config", "user.email", check=False, capture=True).stdout.strip():
        git("config", "user.email", "Nishanth091123@users.noreply.github.com")  # keeps your real email private

    # 1) .env must be ignored
    if git("check-ignore", "-q", ".env", check=False).returncode != 0:
        sys.exit("[STOP] .env is NOT ignored by git. .gitignore must contain the line  .env")
    tracked = git("ls-files", "--cached", capture=True).stdout.split()
    if any(Path(t).name == ".env" for t in tracked):
        git("rm", "--cached", "-q", ".env")
        print("[FIXED] .env was tracked earlier – removed from git (your file stays on the PC)")

    # 2) list exactly what would be uploaded, scan it for keys
    files = git("ls-files", "--cached", "--others", "--exclude-standard", capture=True).stdout.splitlines()
    secrets = env_values()
    bad = []
    for f in files:
        p = ROOT / f
        if not p.is_file() or p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(v in text for v in secrets) or any(re.search(pt, text) for pt in PATTERNS):
            bad.append(f)
    if bad:
        print("[STOP] These files contain something that looks like a key / password – nothing was pushed:")
        for b in bad:
            print("   ", b)
        print("Remove the key from the file (keys belong only in .env) and run again.")
        return 1
    print(f"[OK] Secret check passed ({len(files)} files, .env not included)")

    # 3) commit + push
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode != 0:
        git("commit", "-q", "-m", msg)
        print("[OK] Committed:", msg)
    else:
        print("Nothing new to commit")
    git("branch", "-M", "main")
    remotes = git("remote", capture=True).stdout.split()
    if "origin" not in remotes:
        git("remote", "add", "origin", REMOTE)
    # bring in any change made on the GitHub website first (avoids "rejected – fetch first")
    if git("ls-remote", "--heads", "origin", "main", check=False, capture=True).stdout.strip():
        r = git("pull", "--rebase", "origin", "main", check=False, capture=True)
        if r.returncode != 0:
            git("rebase", "--abort", check=False, capture=True)
            print("[FAIL] GitHub has changes that clash with this PC. Send this message to Claude.")
            return 1
    print("Pushing to", REMOTE, "...")
    r = git("push", "-u", "origin", "main", check=False)
    if r.returncode != 0:
        print("[FAIL] Push did not work. Check: the repository exists on GitHub and is EMPTY, and you logged in.")
        print("       If GitHub says 'rejected (fetch first)', the repo is not empty – make it again without README.")
        return 1
    print("[OK] PUSHED: https://github.com/Nishanth091123/Nexora-Build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
