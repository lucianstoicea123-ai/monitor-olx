from html import escape

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response

app = FastAPI(
    title="Monitor OLX",
    description="Platformă de monitorizare a anunțurilor OLX.",
)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> str:
    canonical_url = escape(str(request.base_url), quote=True)
    return f"""
    <!DOCTYPE html>
    <html lang="ro">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Monitor OLX - Platformă</title>
            <meta name="description" content="Monitorizează căutările și anunțurile OLX dintr-un singur loc. Configurează căutările pe care vrei să le urmărești.">
            <link rel="canonical" href="{canonical_url}">
            <meta property="og:type" content="website">
            <meta property="og:title" content="Monitor OLX - Platformă">
            <meta property="og:description" content="Monitorizează căutările și anunțurile OLX dintr-un singur loc.">
            <meta property="og:url" content="{canonical_url}">
        </head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px; background-color: #121212; color: #ffffff;">
            <h1>Bun venit pe platforma ta de Monitorizare OLX!</h1>
            <p>Aici va fi panoul de control unde utilizatorii își vor seta căutările.</p>
            <div style="background: #1e1e1e; padding: 20px; display: inline-block; border-radius: 8px;">
                <h3>Setări Căutare</h3>
                <input type="text" placeholder="Ce cauți pe OLX?" style="padding: 10px; width: 250px;"><br><br>
                <button style="padding: 10px 20px; background: #00ff66; border: none; font-weight: bold; cursor: pointer;">Pornește Căutarea</button>
            </div>
        </body>
    </html>
    """


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request) -> Response:
    sitemap_url = escape(f"{request.base_url}sitemap.xml", quote=True)
    return Response(
        content=f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n",
        media_type="text/plain",
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request) -> Response:
    page_url = escape(str(request.base_url), quote=True)
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{page_url}</loc></url>\n"
            "</urlset>"
        ),
        media_type="application/xml",
    )
