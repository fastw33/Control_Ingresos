# app/security/cors.py
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://www.appfastway.com",  #
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",  
        allow_credentials=True,
        allow_methods=["*"],  
        allow_headers=["*"],
        max_age=86400,         # cache del preflight (24h)
    )
