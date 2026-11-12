"""On-demand, read-only checks for the dashboard's actual dependencies."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
import socket
import ssl
from time import perf_counter

from dashboard.auth import LDAPSettings
from dashboard.loadings import QUERY_PATH


DATABASE_CHECKS = {
    "Hive": ("HIVE", 10000, "Cloudera ODBC Driver for Apache Hive"),
    "Datamart": ("DATAMART", 21050, "Cloudera ODBC Driver for Impala"),
    "GSYSTEM": ("GSYSTEM", 3306, None),
    "MMS": ("MMS", 3306, None),
    "FEX": ("FEX", 1433, "ODBC Driver 17 for SQL Server"),
}
CHECK_OPTIONS = ("All", "LDAP", "Engage SQL", *DATABASE_CHECKS, "Query file")


@dataclass
class CheckResult:
    check: str
    status: str
    detail: str
    elapsed_ms: int = 0


def sql_failure_detail(error: Exception) -> str:
    code = str(error.args[0]) if error.args else ""
    messages = {
        "08001": "SQL Server connection failed. Check the server address, SQL port, firewall, and network access.",
        "08S01": "The connection to SQL Server was interrupted.",
        "28000": "SQL login was rejected. The Windows account running the app needs database access.",
        "HYT00": "The SQL operation timed out. Check network access and server responsiveness.",
        "HYT01": "The SQL connection timed out. Check the SQL port, firewall, and network access.",
        "IM002": "ODBC Driver 17 for SQL Server is missing or unavailable to this Python environment.",
        "IM003": "The SQL Server ODBC driver could not be loaded.",
        "42000": "SQL rejected the query. Check table-read permissions and the query schema.",
        "42S02": "An Engage table or view was not found.",
        "42S22": "An Engage query column was not found.",
    }
    if code in messages:
        return f"{messages[code]} (ODBC {code})"
    if isinstance(error, ImportError):
        return "Database dependencies are missing. Restart run-local.bat to install the bundled packages."
    return "The SQL check failed. Verify the Okada configuration and database access."


def _check(name, operation) -> CheckResult:
    started = perf_counter()
    try:
        detail = operation()
        status = "Passed"
    except Exception as error:
        status = "Failed"
        if isinstance(error, socket.gaierror):
            detail = "The server name could not be resolved. Check DNS and the network connection."
        elif isinstance(error, TimeoutError):
            detail = "Connection timed out. Check the server port, firewall, and network access."
        elif isinstance(error, ConnectionRefusedError):
            detail = "The server refused the connection. Check the service and port."
        else:
            detail = "The check failed. Verify the service configuration and access."
    return CheckResult(name, status, detail, round((perf_counter() - started) * 1000))


def _dns(host):
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    return f"{host}: {', '.join(addresses)}"


def _tcp(host, port):
    with socket.create_connection((host, port), timeout=5):
        return f"{host}:{port} is reachable."


def check_ldap(values=None) -> list[CheckResult]:
    from urllib.parse import urlsplit
    try:
        settings = LDAPSettings.from_mapping(values)
    except Exception:
        return [CheckResult("LDAP configuration", "Failed", "LDAP configuration is missing or invalid.")]
    parsed = urlsplit(settings.server)
    port = parsed.port or (636 if parsed.scheme == "ldaps" else 389)
    results = [_check("LDAP DNS", lambda: _dns(parsed.hostname)),
               _check("LDAP port", lambda: _tcp(parsed.hostname, port))]
    if results[-1].status != "Passed":
        results.append(CheckResult("LDAP TLS", "Skipped", "The directory port is unreachable."))
        return results
    started = perf_counter()
    connection = None
    try:
        from ldap3 import Connection, Server, Tls, NONE
        server = Server(settings.server, get_info=NONE, connect_timeout=5,
                        tls=Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=settings.ca_cert_file))
        connection = Connection(server, receive_timeout=5)
        connection.open(read_server_info=False)
        if connection.closed or (parsed.scheme == "ldap" and not connection.start_tls()):
            raise RuntimeError("TLS unavailable")
        result = CheckResult("LDAP TLS", "Passed", "Secure connection and server certificate verified. No user login was attempted.")
    except Exception:
        result = CheckResult("LDAP TLS", "Failed", "Secure directory connection failed. Check the server certificate, hostname, CA bundle, and TLS support.")
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                pass
    result.elapsed_ms = round((perf_counter() - started) * 1000)
    results.append(result)
    return results


def check_engage() -> list[CheckResult]:
    try:
        import pyodbc
        from okada import SQL
        loader = SQL("Engage").get_loader()
    except Exception as error:
        return [CheckResult("Okada SQL helper", "Failed", sql_failure_detail(error))]
    results = [_check("Engage DNS", lambda: _dns(loader.server)),
               _check("Engage port", lambda: _tcp(loader.server, 1433))]
    # This probe assumes the default port used by the current HALO loader. The
    # real connector below remains authoritative, even when the TCP probe fails.
    try:
        driver_ok = "ODBC Driver 17 for SQL Server" in pyodbc.drivers()
    except Exception:
        driver_ok = False
    results.append(CheckResult("SQL ODBC driver", "Passed" if driver_ok else "Failed",
                               "ODBC Driver 17 for SQL Server is installed." if driver_ok else
                               "Install 64-bit ODBC Driver 17 for SQL Server on the app host."))
    if not driver_ok:
        results.append(CheckResult("Engage login", "Skipped", "The required ODBC driver is unavailable."))
        results.append(CheckResult("Engage table access", "Skipped", "A SQL connection is required."))
        return results
    started = perf_counter()
    try:
        with closing(loader._get_conn()) as connection:
            connection.timeout = 10
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                results.append(CheckResult("Engage login", "Passed", "SQL connection and Windows authentication succeeded.",
                                           round((perf_counter() - started) * 1000)))
                started = perf_counter()
                try:
                    # Verify the two loading tables/columns without fetching patron rows.
                    cursor.execute("""SELECT TOP (0) ba.TransEmployee, p.Universalplayerid,
                        ba.AdjustmentDate, ba.AdjustmentAmount, ba.AdjustmentAction
                        FROM ENGAGEDB.dbo.UC_PL_BucketAdjustment ba
                        LEFT JOIN ENGAGEDB.dbo.uc_pl_player p ON p.PlayerID = ba.PlayerID""")
                    results.append(CheckResult("Engage table access", "Passed", "The loading tables and required columns are readable; no patron rows fetched.",
                                               round((perf_counter() - started) * 1000)))
                except Exception as error:
                    results.append(CheckResult("Engage table access", "Failed", sql_failure_detail(error),
                                               round((perf_counter() - started) * 1000)))
    except Exception as error:
        results.append(CheckResult("Engage login", "Failed", sql_failure_detail(error),
                                   round((perf_counter() - started) * 1000)))
        results.append(CheckResult("Engage table access", "Skipped", "The SQL connection failed."))
    return results


def check_database(name: str) -> list[CheckResult]:
    system, default_port, driver = DATABASE_CHECKS[name]
    try:
        from okada import SQL
        loader = SQL(system).get_loader()
    except Exception:
        return [CheckResult(f"{name} configuration", "Failed",
                            "The database helper could not be loaded. Check the bundled packages and Okada configuration.")]

    results = [_check(f"{name} DNS", lambda: _dns(loader.server)),
               _check(f"{name} port", lambda: _tcp(loader.server, getattr(loader, "port", default_port)))]
    if driver:
        try:
            import pyodbc
            driver_ok = driver in pyodbc.drivers()
        except Exception:
            driver_ok = False
        results.append(CheckResult(f"{name} ODBC driver", "Passed" if driver_ok else "Failed",
                                   f"{driver} is installed." if driver_ok else
                                   f"Install {driver} for the Python environment running the app."))
        if not driver_ok:
            results.append(CheckResult(f"{name} login/query", "Skipped", "The required ODBC driver is unavailable."))
            return results

    started = perf_counter()
    try:
        # Use the same connector and credentials as the application. The actual
        # connection remains authoritative even when the separate TCP probe fails.
        options = {} if system == "FEX" else {"timeout": 10}
        with closing(loader._get_conn(**options)) as connection:
            if driver:
                connection.timeout = 10
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        result = CheckResult(f"{name} login/query", "Passed",
                             "Database connection and SELECT 1 succeeded; no application rows fetched.")
    except Exception as error:
        code = str(error.args[0]) if error.args else ""
        if isinstance(error, ImportError):
            detail = "Database dependencies are missing. Restart run-local.bat to install the bundled packages."
        elif code in ("28000", "1045"):
            detail = "Database login was rejected. Check the configured credentials and account access."
        elif code in ("HYT00", "HYT01") or isinstance(error, TimeoutError):
            detail = "The database operation timed out. Check network access and server responsiveness."
        else:
            detail = "Database connection or SELECT 1 failed. Check the server, network, configured credentials, and database access."
        result = CheckResult(f"{name} login/query", "Failed", detail)
    result.elapsed_ms = round((perf_counter() - started) * 1000)
    results.append(result)
    return results


def check_query_file() -> list[CheckResult]:
    try:
        query = QUERY_PATH.read_text(encoding="utf-8-sig")
        if not query.strip():
            raise ValueError("empty query")
        return [CheckResult("Loadings query file", "Passed", "queries/engage/Loadings.sql exists and is readable. This check does not execute the file.")]
    except (OSError, UnicodeError, ValueError):
        return [CheckResult("Loadings query file", "Failed", "queries/engage/Loadings.sql is missing, empty, or unreadable. Restart the local launcher.")]


def run_checks(selection: str, ldap_values=None) -> list[dict]:
    results = []
    if selection in ("All", "LDAP"):
        results.extend(check_ldap(ldap_values))
    if selection in ("All", "Engage SQL"):
        results.extend(check_engage())
    for name in DATABASE_CHECKS:
        if selection in ("All", name):
            results.extend(check_database(name))
    if selection in ("All", "Query file"):
        results.extend(check_query_file())
    return [asdict(result) for result in results]
