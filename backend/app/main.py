from fastapi import FastAPI, HTTPException

from sqlalchemy import text

from backend.app import models

from backend.app.database import Base, engine

from backend.routes.ai import router as ai_router

from backend.routes.donations import router as donations_router

from backend.routes.assets import router as assets_router

from backend.routes.maintenance import router as maintenance_router
from backend.routes.finance import router as finance_router

Base.metadata.create_all(bind=engine)


app = FastAPI(title="Temple Management API", version="1.0.0")


app.include_router(donations_router)

app.include_router(ai_router)

app.include_router(assets_router)

app.include_router(maintenance_router)

app.include_router(finance_router)


@app.get("/")
def root():
    return {"message": "Temple Management API is running"}


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"database": "connected"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=("Database connection failed: " f"{str(e)}")
        )
