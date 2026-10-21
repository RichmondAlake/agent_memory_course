#!/usr/bin/env python3
"""Oracle Database Free in user space, for notebook images without Docker or root.

The O'Reilly notebook platform builds images with repo2docker and runs them as an ordinary user, so the
notebook cannot start Oracle with Docker the way part7/oracle.sh does. This script takes the same database
(the gvenzl/oracle-free:23 image) apart instead: it downloads the image's layers straight from the registry,
keeps only the Oracle software and its pre-created database, relocates them under ~/.oracle-free, and runs
them as the current user.

    python oracle_free.py install   # build time (postBuild): download, relocate, provision, shut down cleanly
    python oracle_free.py start     # launch time (start): listener + database, in the background
    python oracle_free.py status    # is FREEPDB1 open?

The result matches oracle.sh: service FREEPDB1 on localhost:1521, user VECTOR / VectorPwd_2025 with the
same grants, and a 512 MB vector memory pool for HNSW indexes.
"""
from __future__ import annotations

import grp
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

IMAGE = "gvenzl/oracle-free"
TAG = os.environ.get("ORACLE_FREE_TAG", "23")
ROOT = Path(os.environ.get("ORACLE_FREE_ROOT", Path.home() / ".oracle-free"))
SID, PDB = "FREE", "FREEPDB1"
SYS_PASSWORD = os.environ.get("ORACLE_SYS_PASSWORD", "Free_Db_Admin_2026")  # orapwd rejects passwords containing "oracle"
APP_USER = os.environ.get("ORACLE_USER", "VECTOR")
APP_PASSWORD = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
STATIC_SERVICE = f"{SID}_STATIC"  # lets SYSDBA start an idle instance over the listener, with the password file
KEEP = ("opt/oracle/", "usr/bin/7zzs",  # the Oracle tree, the 7-Zip that unpacks its database, and the libraries
        "usr/lib64/libaio.so", "usr/lib64/libgfortran.so", "usr/lib64/libquadmath.so")  # Ubuntu lacks (or renames)


def log(msg: str) -> None:
    print(f"[oracle-free] {msg}", flush=True)


# ── 1. fetch the image's files without Docker ─────────────────────────────────────
def _registry_get(url: str, token: str, accept: str):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": accept})
    return urllib.request.urlopen(req, timeout=600)


def fetch(dest: Path) -> None:
    """Download the image from GHCR and extract only the Oracle files, applying layers (and whiteouts) in order."""
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine()]
    token = json.load(urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{IMAGE}:pull", timeout=60))["token"]
    accept_index = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"
    accept_manifest = "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
    index = json.load(_registry_get(f"https://ghcr.io/v2/{IMAGE}/manifests/{TAG}", token, f"{accept_index}, {accept_manifest}"))
    if "manifests" in index:
        digest = next(m["digest"] for m in index["manifests"] if m.get("platform", {}).get("architecture") == arch)
        manifest = json.load(_registry_get(f"https://ghcr.io/v2/{IMAGE}/manifests/{digest}", token, accept_manifest))
    else:
        manifest = index
    layers = manifest["layers"]
    log(f"{IMAGE}:{TAG} ({arch}): {len(layers)} layers, {sum(l['size'] for l in layers) / 1e9:.2f} GB compressed")
    dest.mkdir(parents=True, exist_ok=True)
    for n, layer in enumerate(layers, 1):
        started = time.time()
        with _registry_get(f"https://ghcr.io/v2/{IMAGE}/blobs/{layer['digest']}", token, "*/*") as blob, \
                tarfile.open(fileobj=blob, mode="r|*") as tar:
            for member in tar:
                name = member.name.lstrip("./")
                if not name.startswith(KEEP):
                    continue
                target = dest / name
                base = os.path.basename(name)
                if base.startswith(".wh."):  # a whiteout: this layer deletes a file from an earlier one
                    victim = target.parent / base[4:]
                    shutil.rmtree(victim, ignore_errors=True) if victim.is_dir() else victim.unlink(missing_ok=True)
                    continue
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or target.exists():
                    target.unlink()
                if member.issym():
                    target.symlink_to(member.linkname)
                elif member.islnk():
                    source = dest / member.linkname.lstrip("./")
                    if source.exists():
                        shutil.copy2(source, target)
                elif member.isfile():
                    with tar.extractfile(member) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out, 1 << 20)
                    os.chmod(target, member.mode | 0o600)
        log(f"  layer {n}/{len(layers)} ({layer['size'] / 1e6:.0f} MB) in {time.time() - started:.0f}s")


# ── 2. paths and environment ───────────────────────────────────────────────────────
def oracle_home() -> Path:
    return next((ROOT / "opt/oracle/product").glob("*/dbhomeFree"))


def env() -> dict:
    home = oracle_home()
    e = dict(os.environ, ORACLE_HOME=str(home), ORACLE_BASE=str(ROOT / "opt/oracle"), ORACLE_SID=SID,
             TNS_ADMIN=str(home / "network/admin"), NLS_LANG="AMERICAN_AMERICA.AL32UTF8")
    e["LD_LIBRARY_PATH"] = os.pathsep.join([str(home / "lib"), str(ROOT / "usr/lib64"), e.get("LD_LIBRARY_PATH", "")])
    e["PATH"] = os.pathsep.join([str(home / "bin"), e["PATH"]])
    return e


def run(cmd: list[str], stdin: str | None = None, check: bool = True) -> str:
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env())
    out = (r.stdout + r.stderr).strip()
    if check and r.returncode:
        raise SystemExit(f"[oracle-free] {' '.join(cmd[:2])} failed ({r.returncode}):\n{out[-3000:]}")
    return out


def sysdba(sql: str, check: bool = True) -> str:
    """SYSDBA through the listener's static entry: works on an idle instance, authenticated by the password file."""
    script = f"WHENEVER SQLERROR EXIT SQL.SQLCODE\nSET HEADING OFF FEEDBACK OFF PAGESIZE 0 LINESIZE 400\n{sql}\nEXIT\n"
    out = run(["sqlplus", "-S", "-L", f"sys/{SYS_PASSWORD}@//localhost:1521/{STATIC_SERVICE} as sysdba"], script, check)
    if check and any(code in out for code in ("ORA-", "SP2-")):
        raise SystemExit(f"[oracle-free] SQL failed:\n{sql[:400]}\n---\n{out[-3000:]}")
    return out


def write_network_files() -> None:
    home, base = oracle_home(), ROOT / "opt/oracle"
    admin = home / "network/admin"
    (admin / "listener.ora").write_text(f"""LISTENER =
  (DESCRIPTION_LIST =
    (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = 0.0.0.0)(PORT = 1521))))

SID_LIST_LISTENER =
  (SID_LIST =
    (SID_DESC = (GLOBAL_DBNAME = {STATIC_SERVICE})(ORACLE_HOME = {home})(SID_NAME = {SID})))

DEFAULT_SERVICE_LISTENER = {SID}
ADR_BASE_LISTENER = {base}
""")
    (admin / "tnsnames.ora").write_text(f"""{SID} = (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = localhost)(PORT = 1521))
  (CONNECT_DATA = (SERVER = DEDICATED)(SERVICE_NAME = {SID})))
{PDB} = (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = localhost)(PORT = 1521))
  (CONNECT_DATA = (SERVER = DEDICATED)(SERVICE_NAME = {PDB})))
""")
    (home / "oraInst.loc").write_text(f"inventory_loc={base / 'oraInventory'}\ninst_group={grp.getgrgid(os.getgid()).gr_name}\n")


def write_pfile() -> Path:
    base = ROOT / "opt/oracle"
    data = base / "oradata" / SID
    (base / "admin" / SID / "adump").mkdir(parents=True, exist_ok=True)
    pfile = oracle_home() / "dbs" / f"init{SID}.ora"
    pfile.write_text(f"""db_name='{SID}'
compatible='23.6.0'
control_files='{data}/control01.ctl','{data}/control02.ctl'
diagnostic_dest='{base}'
enable_pluggable_database=true
sga_target=1536m
pga_aggregate_target=512m
vector_memory_size=512M
processes=200
open_cursors=300
undo_tablespace='UNDOTBS1'
remote_login_passwordfile='EXCLUSIVE'
local_listener=''
dispatchers='(PROTOCOL=TCP) (SERVICE={SID}XDB)'
shared_servers=0
job_queue_processes=1
cpu_count=2
common_user_prefix=''
nls_language='AMERICAN'
nls_territory='AMERICA'
control_management_pack_access='DIAGNOSTIC+TUNING'
_enable_memory_protection_keys=FALSE
_dmm_blas_library='libora_netlib.so'
fast_start_parallel_rollback='FALSE'
""")
    return pfile


def listener(action: str) -> None:
    out = run(["lsnrctl", action], check=False)
    if action == "start" and "TNS-01106" not in out and "completed successfully" not in out and "already" not in out:
        raise SystemExit(f"[oracle-free] listener did not start:\n{out[-2000:]}")


def keeper() -> None:
    """Parent of every database process: a child subreaper that starts the listener and reaps whatever exits.

    The listener's dedicated server starts the instance, so all of Oracle's background processes descend from
    here. Without a reaper they linger as zombies once they exit (a notebook pod or a build container rarely has
    an init that reaps), and Oracle's own liveness checks then hang SHUTDOWN (ORA-00600 ksb_shut_detached_process3).
    """
    import ctypes
    import signal

    ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    listener("start")
    while True:
        try:
            os.wait()
        except ChildProcessError:
            time.sleep(1)


def keeper_running() -> bool:
    pid_file = ROOT / "keeper.pid"
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text()), 0)
        return True
    except (OSError, ValueError):
        return False


def start_keeper() -> None:
    if keeper_running():
        return
    out = open(ROOT / "keeper.log", "a")
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "keeper"], env=env(),
                            stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True)
    (ROOT / "keeper.pid").write_text(str(proc.pid))
    wait_for_static_service()


def stop_keeper() -> None:
    if keeper_running():
        listener("stop")
        os.kill(int((ROOT / "keeper.pid").read_text()), 15)
    (ROOT / "keeper.pid").unlink(missing_ok=True)


def wait_for_static_service(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if STATIC_SERVICE.upper() in run(["lsnrctl", "status"], check=False).upper():
            return
        time.sleep(1)


# ── 3. install (build time) ──────────────────────────────────────────────────────
def install() -> None:
    started = time.time()
    if (ROOT / ".installed").exists():
        log(f"already installed at {ROOT}")
        return
    if not (ROOT / ".fetched").exists():  # a retry after a later failure keeps the download
        shutil.rmtree(ROOT, ignore_errors=True)
        fetch(ROOT)
        archive = ROOT / "opt/oracle" / f"{SID}.7z"
        if archive.exists():  # gvenzl ships the pre-created database compressed; the image unpacks it on first start
            log("unpacking the pre-created database…")
            run([str(ROOT / "usr/bin/7zzs"), "x", "-y", str(archive), f"-o{ROOT / 'opt/oracle/oradata'}"])
            archive.unlink()
        (ROOT / ".fetched").write_text("ok")
    home, base = oracle_home(), ROOT / "opt/oracle"
    log(f"ORACLE_HOME={home}")
    for stale in ("spfile*.ora", "init*.ora", "orapw*", "lk*", "hc_*"):
        for f in (home / "dbs").glob(stale):
            f.unlink()
    write_network_files()
    pfile = write_pfile()
    run(["orapwd", f"file={home / 'dbs' / ('orapw' + SID)}", f"password={SYS_PASSWORD}", "format=12.2", "force=y"])
    start_keeper()
    log("relocating the database to its new path…")
    sysdba(f"STARTUP NOMOUNT PFILE='{pfile}'\nCREATE SPFILE FROM PFILE='{pfile}';\nSHUTDOWN ABORT")
    sysdba("STARTUP MOUNT")
    names = sysdba("SELECT name FROM v$datafile UNION ALL SELECT name FROM v$tempfile UNION ALL SELECT member FROM v$logfile;")
    renames = [f"ALTER DATABASE RENAME FILE '{n.strip()}' TO '{n.strip().replace('/opt/oracle', str(base), 1)}';"
               for n in names.splitlines() if n.strip().startswith("/opt/oracle")]
    sysdba("\n".join(renames) + "\nALTER DATABASE OPEN;\nALTER PLUGGABLE DATABASE ALL OPEN;\nALTER PLUGGABLE DATABASE ALL SAVE STATE;")
    log(f"renamed {len(renames)} files; provisioning {APP_USER} in {PDB}…")
    sysdba(f"""ALTER SESSION SET CONTAINER = {PDB};
DECLARE n NUMBER; BEGIN
  SELECT COUNT(*) INTO n FROM dba_users WHERE username = UPPER('{APP_USER}');
  IF n = 0 THEN EXECUTE IMMEDIATE 'CREATE USER {APP_USER} IDENTIFIED BY "{APP_PASSWORD}"'; END IF;
END;
/
GRANT CREATE SESSION, RESOURCE, CREATE VIEW, CREATE PROPERTY GRAPH TO {APP_USER};
GRANT CTXAPP TO {APP_USER};
ALTER USER {APP_USER} QUOTA UNLIMITED ON USERS;""")
    if not status():
        raise SystemExit(f"[oracle-free] {APP_USER} cannot log in to {PDB}")
    stop()
    shutil.rmtree(base / "diag", ignore_errors=True)  # build-time logs, not needed in the image
    (base / "diag").mkdir()
    (ROOT / ".installed").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    log(f"installed in {time.time() - started:.0f}s at {ROOT}")


def stop() -> None:
    """Checkpoint and shut down cleanly; if anything still hangs, abort (safe after a checkpoint: the next startup
    recovers in seconds). Then stop the listener and the keeper."""
    if keeper_running():
        sysdba("ALTER SYSTEM CHECKPOINT;", check=False)
        try:
            out = subprocess.run(["sqlplus", "-S", "-L", f"sys/{SYS_PASSWORD}@//localhost:1521/{STATIC_SERVICE} as sysdba"],
                                 input="SHUTDOWN IMMEDIATE\nEXIT\n", capture_output=True, text=True, env=env(), timeout=120)
            log("shutdown: " + " ".join(out.stdout.split())[-120:])
        except subprocess.TimeoutExpired:
            log("SHUTDOWN IMMEDIATE timed out; aborting after the checkpoint")
            sysdba("SHUTDOWN ABORT", check=False)
    stop_keeper()
    log("database stopped")


# ── 4. start (launch time) and status ──────────────────────────────────────────────
def start(wait: bool = False) -> None:
    if not (ROOT / ".installed").exists():
        log(f"not installed at {ROOT}; run `python {Path(__file__).name} install` first")
        return
    write_network_files()  # the host name may differ from build time; the files only use localhost
    start_keeper()
    out = sysdba("STARTUP\nALTER PLUGGABLE DATABASE ALL OPEN;", check=False)
    log("database started" if "ORA-" not in out or "ORA-01081" in out or "ORA-65019" in out else f"startup said:\n{out[-1500:]}")
    if wait:
        status(wait=True)


def status(wait: bool = False) -> bool:
    deadline = time.time() + (120 if wait else 0)
    while True:
        out = run(["sqlplus", "-S", "-L", f"{APP_USER}/{APP_PASSWORD}@//localhost:1521/{PDB}"],
                  "SET HEADING OFF FEEDBACK OFF\nSELECT 'OPEN' FROM dual;\nEXIT\n", check=False)
        if "OPEN" in out:
            log(f"{PDB} is open on localhost:1521; {APP_USER} can log in")
            return True
        if time.time() > deadline:
            log(f"{PDB} is not reachable yet:\n{out[-400:]}")
            return False
        time.sleep(3)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"install": install, "start": lambda: start(wait="--wait" in sys.argv), "status": status, "stop": stop,
     "keeper": keeper}[command]()
