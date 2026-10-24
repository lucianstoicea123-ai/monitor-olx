import threading
import time
from typing import Callable
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from olx_utils import get_listing_url, get_search_url, parse_price


MAX_PRICE_LIMIT = 1_000_000
MAX_RESULTS = 100
MAX_LOG_ENTRIES = 200


def scan_olx(
    search_term: str,
    max_price_lei: float,
    max_price_eur: float,
    log: Callable[[str], None],
) -> list[dict[str, str | float]]:
    search_url = get_search_url(search_term)
    log(f"Verific anunțurile pentru „{search_term}”…")
    results: list[dict[str, str | float]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            cards = page.locator('[data-cy="l-card"]')
            cards.first.wait_for(timeout=15000)
            log(f"Anunțuri găsite pe OLX: {cards.count()}")

            for card in cards.all():
                link_element = card.locator("a[href]").first
                href = link_element.get_attribute("href")
                if not href:
                    continue
                listing_url = get_listing_url(href)
                if listing_url is None:
                    continue

                title_element = card.locator("h4, h6").first
                title = (
                    title_element.inner_text().strip()
                    if title_element.count()
                    else "Fără titlu"
                )
                price_element = card.locator('[data-testid="ad-price"]').first
                if not price_element.count():
                    continue
                parsed_price = parse_price(price_element.inner_text().strip())
                if parsed_price is None:
                    continue
                price, currency = parsed_price
                maximum = max_price_lei if currency == "RON" else max_price_eur
                if price > maximum:
                    continue

                results.append(
                    {
                        "title": title,
                        "price": price,
                        "currency": currency,
                        "link": listing_url,
                    }
                )

            log(f"Anunțuri sub plafonul de preț: {len(results)}")
            return results
        finally:
            browser.close()


class OlxMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: dict[str, object] | None = None

    def start(
        self,
        search_term: str,
        max_price_lei: float,
        max_price_eur: float,
        interval_minutes: int,
    ) -> str:
        with self._lock:
            if self._job is not None and self._job["status"] == "running":
                raise ValueError("O monitorizare este deja activă.")

            job_id = str(uuid4())
            stop_event = threading.Event()
            self._job = {
                "job_id": job_id,
                "search_term": search_term,
                "status": "running",
                "logs": [],
                "listings": {},
                "error": None,
                "stop_event": stop_event,
            }
            worker = threading.Thread(
                target=self._run,
                args=(
                    job_id,
                    search_term,
                    max_price_lei,
                    max_price_eur,
                    interval_minutes,
                    stop_event,
                ),
                daemon=True,
            )
            worker.start()
            return job_id

    def stop(self, job_id: str) -> bool:
        with self._lock:
            job = self._job
            if (
                job is None
                or job["job_id"] != job_id
                or job["status"] != "running"
            ):
                return False
            stop_event = job["stop_event"]
            assert isinstance(stop_event, threading.Event)
            stop_event.set()
            self._add_log(job, "Se oprește după verificarea curentă.")
            return True

    def status(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._job
            if job is None or job["job_id"] != job_id:
                return None
            listings = job["listings"]
            logs = job["logs"]
            assert isinstance(listings, dict)
            assert isinstance(logs, list)
            return {
                "job_id": job["job_id"],
                "search_term": job["search_term"],
                "status": job["status"],
                "logs": list(logs),
                "listings": list(listings.values()),
                "error": job["error"],
            }

    def _run(
        self,
        job_id: str,
        search_term: str,
        max_price_lei: float,
        max_price_eur: float,
        interval_minutes: int,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            try:
                found = scan_olx(
                    search_term,
                    max_price_lei,
                    max_price_eur,
                    lambda message: self._log(job_id, message),
                )
            except (PlaywrightError, OSError, RuntimeError) as exc:
                self._fail(job_id, str(exc))
                return

            with self._lock:
                job = self._job
                if job is None or job["job_id"] != job_id:
                    return
                listings = job["listings"]
                assert isinstance(listings, dict)
                for listing in found:
                    key = str(listing["link"])
                    listings[key] = listing
                while len(listings) > MAX_RESULTS:
                    listings.pop(next(iter(listings)))
                self._add_log(job, f"Rezultate afișate: {len(listings)}.")

            if stop_event.wait(interval_minutes * 60):
                break

        with self._lock:
            job = self._job
            if job is not None and job["job_id"] == job_id:
                job["status"] = "stopped"
                self._add_log(job, "Monitorizarea s-a oprit.")

    def _log(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._job
            if job is not None and job["job_id"] == job_id:
                self._add_log(job, message)

    def _fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._job
            if job is not None and job["job_id"] == job_id:
                job["status"] = "error"
                job["error"] = message
                self._add_log(job, f"Eroare la verificarea OLX: {message}")

    @staticmethod
    def _add_log(job: dict[str, object], message: str) -> None:
        logs = job["logs"]
        assert isinstance(logs, list)
        logs.append(f"{time.strftime('%H:%M:%S')} — {message}")
        del logs[:-MAX_LOG_ENTRIES]
