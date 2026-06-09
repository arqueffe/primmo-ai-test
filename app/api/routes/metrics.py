from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/summary")
def metrics_summary(request: Request) -> dict:
    metrics_store = request.app.state.metrics_store
    return metrics_store.summary()


@router.get("/history")
def metrics_history(request: Request) -> list[dict]:
    metrics_store = request.app.state.metrics_store
    return metrics_store.history()


@router.get("/operations")
def metrics_operations(request: Request) -> list[dict]:
    metrics_store = request.app.state.metrics_store
    return metrics_store.operations()
