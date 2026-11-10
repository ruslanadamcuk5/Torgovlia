#!/usr/bin/env python3
"""Нагрузочный тест чтения витрины: RPS, задержки и ошибки.

Скрипт использует только стандартную библиотеку Python и держит одно
keep-alive соединение на воркер. Это ближе к реальному браузеру, чем
`urllib` с новым TCP-соединением на каждый запрос.

Генератор можно запускать в несколько процессов (`--processes`): один
Python-процесс упирается в GIL раньше, чем тестируемый сервер — особенно
на 1000 RPS. Процессы делят между собой воркеры и целевой RPS, а результаты
собираются в родителе.

Примеры:
    # 100 арендаторов, 1000 RPS, 30 секунд
    python scripts/loadtest.py --base-url http://127.0.0.1:8000 \\
        --path /api/site --tenants-prefix load --tenants-count 100 \\
        --workers 120 --processes 4 --rate 1000 --duration 30 --min-rps 900

    # Каталог товаров на демо-магазинах
    python scripts/loadtest.py --base-url https://staging.example.by \\
        --path /api/products --tenants odezhda,flowers,meat --workers 50

Код возврата 1, если превышен p95, выросла доля ошибок или не достигнут
минимальный RPS. Так тест можно ставить в CI и релизный чек-лист.
"""

from __future__ import annotations

import argparse
import http.client
import multiprocessing
import ssl
import sys
import threading
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Result:
    latencies: list[float] = field(default_factory=list)
    codes: Counter[int] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    samples: list[str] = field(default_factory=list)


class Worker(threading.Thread):
    def __init__(
        self,
        *,
        index: int,
        args: argparse.Namespace,
        tenants: list[str],
        stop: threading.Event,
        result: Result,
        result_lock: threading.Lock,
        start_at: float,
    ) -> None:
        super().__init__(daemon=True)
        self.index = index
        self.args = args
        self.tenants = tenants
        self.stop = stop
        self.result = result
        self.result_lock = result_lock
        self.start_at = start_at

        parts = urllib.parse.urlsplit(args.base_url)
        self.scheme = parts.scheme or "http"
        self.host = parts.hostname or "127.0.0.1"
        self.port = parts.port or (443 if self.scheme == "https" else 80)
        self.prefix = parts.path.rstrip("/")
        self.path = self.prefix + args.path
        self.context = None
        if self.scheme == "https":
            self.context = ssl.create_default_context()
            if args.insecure:
                self.context.check_hostname = False
                self.context.verify_mode = ssl.CERT_NONE
        self.connection: http.client.HTTPConnection | None = None
        self.next_at = start_at
        self.interval = args.workers / args.rate if args.rate else 0.0

    def _connect(self) -> http.client.HTTPConnection:
        if self.scheme == "https":
            return http.client.HTTPSConnection(
                self.host, self.port, timeout=self.args.timeout, context=self.context
            )
        return http.client.HTTPConnection(self.host, self.port, timeout=self.args.timeout)

    def _headers(self, slug: str | None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Connection": "keep-alive",
            "User-Agent": "torgovlia-loadtest/1.0",
        }
        if slug:
            headers["X-Tenant-Slug"] = slug
        return headers

    def _pace(self) -> None:
        if not self.interval:
            return
        now = time.perf_counter()
        wait = self.next_at - now
        if wait > 0:
            time.sleep(wait)
            self.next_at += self.interval
        else:
            # Отстали сильнее чем на интервал — не копим долг, идём вровень.
            self.next_at = now + self.interval

    def run(self) -> None:
        while not self.stop.is_set():
            self._pace()
            if self.stop.is_set():
                break
            slug = self.tenants[self.index % len(self.tenants)] if self.tenants else None
            started = time.perf_counter()
            try:
                if self.connection is None:
                    self.connection = self._connect()
                self.connection.request("GET", self.path, headers=self._headers(slug))
                response = self.connection.getresponse()
                response.read()
                elapsed = time.perf_counter() - started
                with self.result_lock:
                    self.result.latencies.append(elapsed)
                    self.result.codes[response.status] += 1
                    if response.status >= 400:
                        self.result.errors[f"HTTP {response.status}"] += 1
            except Exception as exc:  # noqa: BLE001 — тест должен собрать все сбои
                elapsed = time.perf_counter() - started
                if self.connection is not None:
                    try:
                        self.connection.close()
                    except OSError:
                        pass
                    self.connection = None
                with self.result_lock:
                    self.result.latencies.append(elapsed)
                    name = f"{type(exc).__name__}: {exc}"
                    self.result.errors[name] += 1
                    if len(self.result.samples) < 5:
                        self.result.samples.append(f"{slug or '-'}: {name}")

        if self.connection is not None:
            try:
                self.connection.close()
            except OSError:
                pass


def percentile(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((value / 100) * (len(ordered) - 1)))))
    return ordered[index]


def build_tenants(args: argparse.Namespace) -> list[str]:
    if args.tenants:
        return [item.strip() for item in args.tenants.split(",") if item.strip()]
    if args.tenants_prefix and args.tenants_count:
        return [f"{args.tenants_prefix}{i:03d}" for i in range(args.tenants_count)]
    return []


def _warmup(args: argparse.Namespace, tenants: list[str]) -> None:
    if not args.warmup:
        return
    warm = Result()
    warm_lock = threading.Lock()
    dummy_stop = threading.Event()
    threads = [
        Worker(
            index=i,
            args=args,
            tenants=tenants,
            stop=dummy_stop,
            result=warm,
            result_lock=warm_lock,
            start_at=time.perf_counter(),
        )
        for i in range(min(args.workers, max(1, args.warmup)))
    ]
    for thread in threads:
        thread.start()
    deadline = time.perf_counter() + 2
    while time.perf_counter() < deadline and sum(warm.codes.values()) < args.warmup:
        time.sleep(0.02)
    dummy_stop.set()
    for thread in threads:
        thread.join(timeout=1)


def run_load(args: argparse.Namespace) -> dict:
    """Один процесс генератора: прогрев, замер, сырые результаты."""
    tenants = build_tenants(args)
    _warmup(args, tenants)

    result = Result()
    lock = threading.Lock()
    stop = threading.Event()
    start_at = time.perf_counter()
    threads = [
        Worker(
            index=i,
            args=args,
            tenants=tenants,
            stop=stop,
            result=result,
            result_lock=lock,
            start_at=start_at,
        )
        for i in range(args.workers)
    ]
    for thread in threads:
        thread.start()

    time.sleep(args.duration)
    stop.set()
    for thread in threads:
        thread.join(timeout=args.timeout + 2)
    elapsed = time.perf_counter() - start_at
    return {
        "latencies": result.latencies,
        "codes": dict(result.codes),
        "errors": dict(result.errors),
        "samples": result.samples,
        "elapsed": elapsed,
    }


def _child(args: argparse.Namespace, queue) -> None:  # noqa: ANN001
    try:
        queue.put(run_load(args))
    except Exception as exc:  # noqa: BLE001 — родитель должен увидеть причину
        queue.put({"fatal": f"{type(exc).__name__}: {exc}"})


def _split(total: int, parts: int) -> list[int]:
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def run_distributed(args: argparse.Namespace) -> list[dict]:
    """Делит воркеры и целевой RPS между процессами и собирает результаты."""
    processes = args.processes
    if processes == 1:
        return [run_load(args)]

    worker_counts = _split(args.workers, processes)
    rate_per_process = (args.rate / processes) if args.rate else 0.0
    warmup_per_process = max(1, args.warmup // processes) if args.warmup else 0
    context = (
        multiprocessing.get_context("fork")
        if "fork" in multiprocessing.get_all_start_methods()
        else multiprocessing.get_context()
    )
    queue = context.Queue()
    procs = []
    for index in range(processes):
        child_args = argparse.Namespace(**vars(args))
        child_args.workers = max(1, worker_counts[index])
        child_args.rate = rate_per_process
        child_args.warmup = warmup_per_process
        process = context.Process(target=_child, args=(child_args, queue), daemon=False)
        process.start()
        procs.append(process)

    results: list[dict] = []
    try:
        for _ in procs:
            results.append(queue.get(timeout=args.duration + args.timeout + 60))
    finally:
        for process in procs:
            process.join(timeout=args.timeout + 5)
            if process.is_alive():
                process.terminate()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Нагрузочный тест чтения витрины")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Адрес стенда")
    parser.add_argument("--path", default="/api/site", help="Путь запроса")
    parser.add_argument("--tenants", help="Список slug через запятую")
    parser.add_argument("--tenants-prefix", default="", help="Префикс slug для генерации")
    parser.add_argument("--tenants-count", type=int, default=0, help="Сколько slug сгенерировать")
    parser.add_argument("--workers", type=int, default=50, help="Параллельных соединений всего")
    parser.add_argument("--processes", type=int, default=1, help="Процессов генератора")
    parser.add_argument("--rate", type=float, default=0, help="Целевой общий RPS (0 — без ограничения)")
    parser.add_argument("--duration", type=float, default=20, help="Длительность, секунд")
    parser.add_argument("--warmup", type=int, default=50, help="Прогревочных запросов")
    parser.add_argument("--timeout", type=float, default=10, help="Таймаут запроса, секунд")
    parser.add_argument("--p95", type=float, default=300, help="Порог p95, мс")
    parser.add_argument("--max-error-rate", type=float, default=1.0, help="Порог ошибок, %")
    parser.add_argument("--min-rps", type=float, default=0, help="Минимальный RPS")
    parser.add_argument("--insecure", action="store_true", help="Не проверять HTTPS-сертификат")
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers должен быть больше нуля")
    if args.processes < 1:
        parser.error("--processes должен быть больше нуля")
    if args.processes > args.workers:
        parser.error("--processes не может быть больше --workers")
    if args.duration <= 0:
        parser.error("--duration должен быть больше нуля")
    if args.rate and args.rate < 1:
        parser.error("--rate должен быть больше нуля или не указан")

    tenants = build_tenants(args)
    label = f"{len(tenants)} арендаторов" if tenants else "без заголовка арендатора"
    print(
        f"→ {args.base_url}{args.path} · {label} · "
        f"{args.workers} воркеров"
        + (f" в {args.processes} процессах" if args.processes > 1 else "")
        + f" · {args.duration:g} c"
        + (f" · цель {args.rate:g} RPS" if args.rate else "")
    )

    started = time.perf_counter()
    results = run_distributed(args)
    wall = time.perf_counter() - started

    fatal = [item["fatal"] for item in results if item.get("fatal")]
    if fatal:
        for message in fatal:
            print(f"  ! процесс генератора упал: {message}")
        print("ИТОГ: FAIL — генератор не смог выполнить тест")
        return 1

    latencies: list[float] = []
    codes: Counter[int] = Counter()
    errors: Counter[str] = Counter()
    samples: list[str] = []
    elapsed = max((item["elapsed"] for item in results), default=wall)
    for item in results:
        latencies.extend(item["latencies"])
        codes.update(item["codes"])
        errors.update(item["errors"])
        for sample in item["samples"]:
            if len(samples) < 5:
                samples.append(sample)

    total = len(latencies)
    error_count = sum(errors.values())
    error_rate = (error_count / total * 100) if total else 100.0
    rps = total / elapsed if elapsed else 0.0
    p50 = percentile(latencies, 50) * 1000
    p95 = percentile(latencies, 95) * 1000
    p99 = percentile(latencies, 99) * 1000
    peak = max(latencies, default=0) * 1000

    print(f"Запросов: {total}, RPS: {rps:.1f}")
    print(
        f"Задержки: p50 {p50:.0f} мс · p95 {p95:.0f} мс · "
        f"p99 {p99:.0f} мс · max {peak:.0f} мс"
    )
    print(f"Ошибки: {error_count} ({error_rate:.2f}%)")
    if codes:
        print("Коды: " + ", ".join(f"{code}={count}" for code, count in sorted(codes.items())))
    for name, count in errors.most_common(5):
        print(f"  ! {count}× {name}")
    for sample in samples:
        print(f"  · {sample}")

    problems: list[str] = []
    if p95 > args.p95:
        problems.append(f"p95 {p95:.0f} мс > {args.p95:g} мс")
    if error_rate > args.max_error_rate:
        problems.append(f"ошибки {error_rate:.2f}% > {args.max_error_rate:g}%")
    if args.min_rps and rps < args.min_rps:
        problems.append(f"RPS {rps:.1f} < {args.min_rps:g}")

    if problems:
        print("ИТОГ: FAIL — " + "; ".join(problems))
        return 1
    print(
        "ИТОГ: OK — "
        f"p95 {p95:.0f} мс ≤ {args.p95:g} мс, ошибки {error_rate:.2f}%"
        + (f", RPS {rps:.1f} ≥ {args.min_rps:g}" if args.min_rps else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
