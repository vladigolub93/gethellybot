__all__ = ["router"]


def __getattr__(name: str):
    if name == "router":
        from src.webapp.router import router

        return router
    raise AttributeError(name)
