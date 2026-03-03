from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from framework.audit_logger import AuditLogger

app = FastAPI(
    title="FinAgent Shield Dashboard",
    description="Monitoring and audit dashboard for financial AI agents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

audit = AuditLogger()


@app.get("/")
def root():
    return {"service": "FinAgent Shield", "status": "running", "version": "1.0.0"}


@app.get("/runs")
def get_runs(limit: int = 50):
    return {"runs": audit.get_all_runs(limit=limit)}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    summary = audit.get_run_summary(run_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Run not found")
    return summary


@app.get("/security/report")
def security_report():
    return audit.get_security_report()


@app.get("/health")
def health():
    return {"status": "healthy"}
