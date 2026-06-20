"""
页面路由
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from web.app import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request})


@router.get("/trades", response_class=HTMLResponse)
async def trades_page(request: Request):
    return templates.TemplateResponse(request, "trades.html", {"request": request})


@router.get("/signals", response_class=HTMLResponse)
async def signals_page(request: Request):
    return templates.TemplateResponse(request, "signals.html", {"request": request})


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    return templates.TemplateResponse(request, "analysis.html", {"request": request})
