from fastapi import FastAPI
from furniture_intelligence.api.routes import router

app = FastAPI(title='CAD Scaler Digitizer Furniture Intelligence API')
app.include_router(router)

# Run:
# uvicorn api_app_example:app --reload --port 8000
