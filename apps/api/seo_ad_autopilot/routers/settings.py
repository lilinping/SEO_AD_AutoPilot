from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import json
from pathlib import Path

router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_FILE = Path("var/seo-ad-autopilot.db") # placeholder for settings file or db
# For simplicity, we can store dynamic user configurations in a settings.json file inside var/
CONFIG_JSON_PATH = Path("var/settings.json")

class SettingsPayload(BaseModel):
    # General Settings
    autoDeploy: Optional[bool] = False
    approvalThreshold: Optional[int] = 60
    blockThreshold: Optional[int] = 80
    monitorWindow: Optional[int] = 90
    rollbackWindow: Optional[int] = 5
    autoCruise: Optional[bool] = False
    strictProviders: Optional[bool] = False
    
    # Env / API settings
    apiKey: Optional[str] = ""
    databaseUrl: Optional[str] = ""
    redisUrl: Optional[str] = ""

@router.get("")
def get_settings():
    CONFIG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Default values matching frontend defaults
    data = {
        "autoDeploy": False,
        "approvalThreshold": 60,
        "blockThreshold": 80,
        "monitorWindow": 90,
        "rollbackWindow": 5,
        "autoCruise": False,
        "strictProviders": False,
        "apiKey": os.getenv("SEO_AD_BOT_API_KEY", ""),
        "databaseUrl": os.getenv("DATABASE_URL", "sqlite:///./var/seo-ad-autopilot.db"),
        "redisUrl": os.getenv("REDIS_URL", "redis://localhost:6379/0")
    }
    
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                data.update(saved)
        except Exception:
            pass
            
    return data

@router.post("")
def save_settings(payload: SettingsPayload):
    CONFIG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    data = payload.model_dump()
    
    try:
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")
        
    # Dynamically apply settings to environment if needed
    if payload.apiKey:
        os.environ["SEO_AD_BOT_API_KEY"] = payload.apiKey
    if payload.databaseUrl:
        os.environ["DATABASE_URL"] = payload.databaseUrl
    if payload.redisUrl:
        os.environ["REDIS_URL"] = payload.redisUrl
        
    return {"status": "success", "message": "Settings saved successfully"}
