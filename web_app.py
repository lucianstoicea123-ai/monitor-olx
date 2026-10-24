from html import escape

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from olx_web_monitor import MAX_PRICE_LIMIT, OlxMonitor

app = FastAPI(
    title="Monitor OLX",
    description="Platformă de monitorizare a anunțurilor OLX.",
)
monitor = OlxMonitor()


class SearchRequest(BaseModel):
    search_term: str = Field(min_length=1, max_length=100)
    max_price_lei: float = Field(default=MAX_PRICE_LIMIT, ge=0, le=MAX_PRICE_LIMIT)
    max_price_eur: float = Field(default=MAX_PRICE_LIMIT, ge=0, le=MAX_PRICE_LIMIT)
    interval_minutes: int = Field(default=15, ge=1, le=1440)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> str:
    canonical_url = escape(str(request.base_url), quote=True)
    html_document = """
    <!DOCTYPE html>
    <html lang="ro">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Monitor OLX - Platformă</title>
            <meta name="description" content="Monitorizează căutările și anunțurile OLX dintr-un singur loc. Configurează căutările pe care vrei să le urmărești.">
            <link rel="canonical" href="__CANONICAL_URL__">
            <meta property="og:type" content="website">
            <meta property="og:title" content="Monitor OLX - Platformă">
            <meta property="og:description" content="Monitorizează căutările și anunțurile OLX dintr-un singur loc.">
            <meta property="og:url" content="__CANONICAL_URL__">
        </head>
        <body style="font-family: Arial, sans-serif; margin: 40px auto; max-width: 900px; padding: 0 20px; background-color: #121212; color: #ffffff;">
            <h1>Bun venit pe platforma ta de Monitorizare OLX!</h1>
            <p>Urmărește anunțurile OLX după termen și plafon de preț.</p>
            <form id="search-form" style="background: #1e1e1e; padding: 20px; border-radius: 8px;">
                <h2>Setări căutare</h2>
                <label for="search-term">Ce cauți pe OLX?</label><br>
                <input id="search-term" name="search_term" type="text" maxlength="100" required
                    placeholder="ex. bicicletă" style="padding: 10px; width: min(100%, 350px); box-sizing: border-box;"><br><br>
                <label for="max-lei">Preț maxim (RON)</label><br>
                <input id="max-lei" name="max_price_lei" type="number" min="0" max="1000000" step="any" value="1000000" required
                    style="padding: 10px; width: 180px;"><br><br>
                <label for="max-eur">Preț maxim (EUR)</label><br>
                <input id="max-eur" name="max_price_eur" type="number" min="0" max="1000000" step="any" value="1000000" required
                    style="padding: 10px; width: 180px;"><br><br>
                <label for="interval">Verifică la fiecare (minute)</label><br>
                <input id="interval" name="interval_minutes" type="number" min="1" max="1440" value="15" required
                    style="padding: 10px; width: 180px;"><br><br>
                <button id="start-button" type="submit" style="padding: 10px 20px; background: #00ff66; border: none; font-weight: bold; cursor: pointer;">Pornește căutarea</button>
                <button id="stop-button" type="button" disabled style="padding: 10px 20px; cursor: pointer;">Oprește</button>
                <p id="status" role="status">Oprit</p>
            </form>
            <section aria-live="polite">
                <h2>Anunțuri găsite</h2>
                <ul id="results"></ul>
                <h2>Activitate</h2>
                <pre id="logs" style="white-space: pre-wrap; background: #1e1e1e; padding: 15px; border-radius: 8px;"></pre>
                <p id="error" role="alert" style="color: #ff7777;"></p>
            </section>
            <script>
                const form = document.getElementById("search-form");
                const startButton = document.getElementById("start-button");
                const stopButton = document.getElementById("stop-button");
                const statusText = document.getElementById("status");
                const results = document.getElementById("results");
                const logs = document.getElementById("logs");
                const errorText = document.getElementById("error");
                let jobId = null;
                let pollTimer = null;

                form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    errorText.textContent = "";
                    startButton.disabled = true;
                    const data = Object.fromEntries(new FormData(form));
                    data.max_price_lei = Number(data.max_price_lei);
                    data.max_price_eur = Number(data.max_price_eur);
                    data.interval_minutes = Number(data.interval_minutes);
                    try {
                        const response = await fetch("/api/search", {
                            method: "POST",
                            headers: {"Content-Type": "application/json"},
                            body: JSON.stringify(data)
                        });
                        const body = await response.json();
                        if (!response.ok) throw new Error(body.detail || "Nu s-a putut porni căutarea.");
                        jobId = body.job_id;
                        stopButton.disabled = false;
                        statusText.textContent = "Monitorizare activă";
                        results.replaceChildren();
                        logs.textContent = "";
                        pollTimer = window.setInterval(refreshStatus, 2000);
                        await refreshStatus();
                    } catch (error) {
                        startButton.disabled = false;
                        errorText.textContent = error.message;
                    }
                });

                stopButton.addEventListener("click", async () => {
                    if (!jobId) return;
                    stopButton.disabled = true;
                    try {
                        const response = await fetch(`/api/search/${encodeURIComponent(jobId)}/stop`, {method: "POST"});
                        const body = await response.json();
                        if (!response.ok) throw new Error(body.detail || "Nu s-a putut opri căutarea.");
                        statusText.textContent = "Se oprește…";
                    } catch (error) {
                        errorText.textContent = error.message;
                        stopButton.disabled = false;
                    }
                });

                async function refreshStatus() {
                    if (!jobId) return;
                    try {
                        const response = await fetch(`/api/search/${encodeURIComponent(jobId)}`);
                        const body = await response.json();
                        if (!response.ok) throw new Error(body.detail || "Nu s-a putut citi starea căutării.");
                        statusText.textContent = body.status === "running" ? "Monitorizare activă" :
                            body.status === "error" ? "Eroare" : "Oprit";
                        logs.textContent = body.logs.join("\\n");
                        errorText.textContent = body.error || "";
                        results.replaceChildren(...body.listings.map((item) => {
                            const li = document.createElement("li");
                            const link = document.createElement("a");
                            link.href = item.link;
                            link.target = "_blank";
                            link.rel = "noopener noreferrer";
                            link.textContent = `${item.title} — ${item.price} ${item.currency}`;
                            li.append(link);
                            return li;
                        }));
                        if (body.status !== "running") {
                            window.clearInterval(pollTimer);
                            startButton.disabled = false;
                            stopButton.disabled = true;
                        }
                    } catch (error) {
                        errorText.textContent = error.message;
                        window.clearInterval(pollTimer);
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }
                }
            </script>
        </body>
    </html>
    """
    return html_document.replace("__CANONICAL_URL__", canonical_url)


@app.post("/api/search")
def start_search(settings: SearchRequest) -> dict[str, str]:
    search_term = settings.search_term.strip()
    if not search_term:
        raise HTTPException(status_code=422, detail="Introdu un termen de căutare.")
    try:
        job_id = monitor.start(
            search_term,
            settings.max_price_lei,
            settings.max_price_eur,
            settings.interval_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job_id": job_id}


@app.get("/api/search/{job_id}")
def search_status(job_id: str) -> dict[str, object]:
    status = monitor.status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Căutarea nu a fost găsită.")
    return status


@app.post("/api/search/{job_id}/stop")
def stop_search(job_id: str) -> dict[str, str]:
    if not monitor.stop(job_id):
        raise HTTPException(
            status_code=404,
            detail="Căutarea nu există sau nu mai este activă.",
        )
    return {"status": "stopping"}


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
