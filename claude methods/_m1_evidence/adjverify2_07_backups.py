import sqlite3, glob, os, re
PAT=re.compile(r"div|split|factor|corp|adjust|复权|除权", re.I)
paths = glob.glob(r"D:\codex-A股交易\output\backups\*.sqlite3") + glob.glob(r"D:\codex-A股交易\logs\backups\*.sqlite3")
for p in paths:
    try:
        c=sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro",uri=True)
        tbls=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        hits=[t for t in tbls if PAT.search(t)]
        extra=""
        if "daily_bars" in tbls:
            n,dmin,dmax=c.execute("SELECT COUNT(*),MIN(substr(available_at,1,10)),MAX(substr(available_at,1,10)) FROM daily_bars").fetchone()
            modes=c.execute("SELECT DISTINCT adjustment_mode FROM daily_bars").fetchall()
            extra=f"  daily_bars rows={n} available_at range=[{dmin}..{dmax}] modes={modes}"
        print(f"{os.path.basename(p):62s} tables={len(tbls):3d} corp-action-named={hits}{extra}")
        c.close()
    except Exception as e:
        print(os.path.basename(p),"ERR",e)
