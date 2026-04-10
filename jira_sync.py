import os
import re
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIGURAÇÕES - JIRA ORIGEM ─────────────────────────────────────────────
SRC_BASE_URL    = os.getenv("SRC_BASE_URL", "https://ti-segurosunimed-soa.atlassian.net")
SRC_EMAIL       = os.getenv("SRC_EMAIL")
SRC_API_TOKEN   = os.getenv("SRC_API_TOKEN")
SRC_ACCOUNT_ID  = os.getenv("SRC_ACCOUNT_ID", "")

# ─── CONFIGURAÇÕES - JIRA DESTINO ────────────────────────────────────────────
DST_BASE_URL    = os.getenv("DST_BASE_URL", "https://jira-uxorit.atlassian.net")
DST_EMAIL       = os.getenv("DST_EMAIL")
DST_API_TOKEN   = os.getenv("DST_API_TOKEN")
DST_ACCOUNT_ID  = os.getenv("DST_ACCOUNT_ID", "")
# ─────────────────────────────────────────────────────────────────────────────

# ─── DE-PARA DE TAREFAS ───────────────────────────────────────────────────────
# Palavras-chave (lowercase) mapeadas para a issue-key no Jira destino
# A busca é feita primeiro no comentário, depois no summary da issue origem.
TASK_MAPPING = [
    (["daily"],                                   "UN-12"),
    (["desenvolvimento", "development"],          "UN-14"),
    (["reunião", "reuniao", "meeting", "reunio"], "UN-24"),
    (["sustentação", "sustentacao", "sustenta"],  "UN-22"),
    (["documentação", "documentacao", "document", "definição", "definicao", "arquitetura"], "UN-26"),
    (["apoio", "apoio time", "support"],          "UN-27"),
    (["teste", "testes"],                         "UN-31"),
]
# ─────────────────────────────────────────────────────────────────────────────

src_session = requests.Session()
if SRC_EMAIL and SRC_API_TOKEN:
    src_session.auth = HTTPBasicAuth(SRC_EMAIL, SRC_API_TOKEN)
src_session.headers.update({"Accept": "application/json"})

dst_session = requests.Session()
if DST_EMAIL and DST_API_TOKEN:
    dst_session.auth = HTTPBasicAuth(DST_EMAIL, DST_API_TOKEN)
dst_session.headers.update({"Accept": "application/json"})


# ─── UTILITÁRIOS ──────────────────────────────────────────────────────────────

def parse_jira_datetime(dt_str):
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    elif len(dt_str) >= 5 and dt_str[-5] in ("+", "-") and dt_str[-3] != ":":
        dt_str = dt_str[:-2] + ":" + dt_str[-2:]
    return datetime.fromisoformat(dt_str)


def seconds_to_hm(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    return f"{h}h{m:02d}m"


def extract_comment(comment_raw):
    if not comment_raw:
        return ""
    if isinstance(comment_raw, dict):
        try:
            parts = []
            for block in comment_raw.get("content", []):
                for node in block.get("content", []):
                    if node.get("type") == "text":
                        parts.append(node.get("text", ""))
            return " ".join(parts).strip()
        except Exception:
            return ""
    return str(comment_raw).strip()


def clean_brackets(text):
    """Remove conteúdo entre colchetes [] e espaços extras."""
    return re.sub(r"\[.*?\]", "", text).strip(" -–")


def match_category(text):
    """Retorna a issue-key destino com base em palavras-chave no texto."""
    normalized = text.lower()
    for keywords, issue_key in TASK_MAPPING:
        for kw in keywords:
            if kw in normalized:
                return issue_key
    return None


def map_to_target_issue(comment, summary):
    """
    Determina a issue-key destino.
    Prioridade: comentário → summary.
    Retorna None se nenhuma categoria for identificada.
    """
    issue_key = match_category(comment) if comment else None
    if not issue_key:
        issue_key = match_category(summary)
    return issue_key


# ─── API - ORIGEM ─────────────────────────────────────────────────────────────

def src_get_account_id():
    r = src_session.get(f"{SRC_BASE_URL}/rest/api/3/myself")
    r.raise_for_status()
    return r.json()["accountId"]


def get_week_range():
    today  = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def src_get_updated_worklog_ids(monday):
    start_ms = int(
        datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=timezone.utc)
        .timestamp() * 1000
    )
    url      = f"{SRC_BASE_URL}/rest/api/3/worklog/updated"
    params   = {"since": start_ms}
    all_ids  = set()

    while True:
        r = src_session.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        for item in data.get("values", []):
            wid = item.get("worklogId")
            if wid is not None:
                all_ids.add(str(wid))
        if data.get("lastPage", True):
            break
        params["since"] = data.get("until", params["since"])

    return all_ids


def src_get_worklogs_by_ids(worklog_ids):
    if not worklog_ids:
        return []
    url          = f"{SRC_BASE_URL}/rest/api/3/worklog/list"
    ids_list     = list(worklog_ids)
    all_worklogs = []

    for i in range(0, len(ids_list), 1000):
        batch = ids_list[i:i + 1000]
        r = src_session.post(url, json={"ids": batch})
        r.raise_for_status()
        all_worklogs.extend(r.json())

    return all_worklogs


_issue_cache = {}

def src_get_issue_summary(issue_id):
    if issue_id in _issue_cache:
        return _issue_cache[issue_id]
    r = src_session.get(
        f"{SRC_BASE_URL}/rest/api/3/issue/{issue_id}",
        params={"fields": "summary"}
    )
    if not r.ok:
        _issue_cache[issue_id] = (issue_id, "(erro)")
        return _issue_cache[issue_id]
    data   = r.json()
    result = (data["key"], data["fields"]["summary"])
    _issue_cache[issue_id] = result
    return result


# ─── API - DESTINO ────────────────────────────────────────────────────────────

def dst_get_account_id():
    r = dst_session.get(f"{DST_BASE_URL}/rest/api/3/myself")
    r.raise_for_status()
    return r.json()["accountId"]


def dst_day_has_worklogs(issue_key, date, account_id):
    r = dst_session.get(
        f"{DST_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    )
    if not r.ok:
        return False
    for wl in r.json().get("worklogs", []):
        author_id  = wl.get("author", {}).get("accountId", "")
        started_dt = parse_jira_datetime(wl.get("started", ""))
        started_date = started_dt.date() if started_dt else None
        if author_id != account_id:
            continue
        if started_date == date:
            return True
    return False


def dst_day_has_any_worklog(date, account_id):
    target_issue_keys = {ik for _, ik in TASK_MAPPING}
    for issue_key in sorted(target_issue_keys):
        if dst_day_has_worklogs(issue_key, date, account_id):
            return True
    return False


def dst_post_worklog(issue_key, started_str, time_seconds, description):
    """Registra um worklog na issue destino."""
    body = {
        "timeSpentSeconds": time_seconds,
        "started": started_str,
        "comment": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description or "-"}]
                }
            ]
        }
    }
    r = dst_session.post(
        f"{DST_BASE_URL}/rest/api/3/issue/{issue_key}/worklog",
        json=body
    )
    return r

def dst_worklog_exists(issue_key, started_str, time_seconds, description, account_id):
    """Verifica se já existe um worklog idêntico considerando o horário de início."""
    r = dst_session.get(
    f"{DST_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    )
    if not r.ok:
        return False
    
    origem_dt = parse_jira_datetime(started_str)
    
    for wl in r.json().get("worklogs", []):
        author_id = wl.get("author", {}).get("accountId", "")
        if author_id != account_id:
            continue
            
        # Converte o horário do destino
        destino_dt = parse_jira_datetime(wl.get("started", ""))
        
        # Compara: Início exato, Tempo e Descrição
        # (Usamos uma tolerância de 1 minuto para o início, caso haja arredondamento de milissegundos)
        same_start = False
        if origem_dt and destino_dt:
            diff = abs((origem_dt - destino_dt).total_seconds())
            same_start = diff < 60 

        same_time = int(wl.get("timeSpentSeconds", 0)) == int(time_seconds)
        
        current_comment = extract_comment(wl.get("comment"))
        same_comment = current_comment.strip() == description.strip()
        
        if same_start and same_time and same_comment:
            return True
            
    return False


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    global SRC_ACCOUNT_ID, DST_ACCOUNT_ID

    print("🔍 Buscando accountId origem...")
    if not SRC_ACCOUNT_ID:
        SRC_ACCOUNT_ID = src_get_account_id()
    print(f"   origem  : {SRC_ACCOUNT_ID}")

    print("🔍 Buscando accountId destino...")
    if not DST_ACCOUNT_ID:
        DST_ACCOUNT_ID = dst_get_account_id()
    print(f"   destino : {DST_ACCOUNT_ID}\n")

    monday, sunday = get_week_range()
    print(f"📅 Semana: {monday.strftime('%d/%m/%Y')} a {sunday.strftime('%d/%m/%Y')}\n")

    print("🔎 Buscando worklogs na origem...")
    worklog_ids = src_get_updated_worklog_ids(monday)
    if not worklog_ids:
        print("Nenhum worklog encontrado na semana.")
        return

    all_worklogs = src_get_worklogs_by_ids(worklog_ids)

    deduped = {}
    for wl in all_worklogs:
        wid = wl.get("id")
        if not wid:
            continue
        if wl.get("author", {}).get("accountId") != SRC_ACCOUNT_ID:
            continue
        started_dt = parse_jira_datetime(wl.get("started", ""))
        if not started_dt:
            continue
        if not (monday <= started_dt.date() <= sunday):
            continue
        if wid in deduped:
            ex_upd = parse_jira_datetime(deduped[wid].get("updated", ""))
            cu_upd = parse_jira_datetime(wl.get("updated", ""))
            if ex_upd and cu_upd and cu_upd <= ex_upd:
                continue
        deduped[wid] = wl

    if not deduped:
        print("Nenhum worklog seu encontrado na semana após filtros.")
        return

    print(f"   {len(deduped)} worklogs encontrados na origem.\n")

    by_day = {}
    for wl in deduped.values():
        started_dt   = parse_jira_datetime(wl["started"])
        started_date = started_dt.date()
        day_key      = started_date.strftime("%Y-%m-%d")
        by_day.setdefault(day_key, []).append(wl)

    print("🔄 Iniciando sincronização...\n")

    for day_key in sorted(by_day.keys()):
        worklogs_do_dia = by_day[day_key]
        day_date        = datetime.strptime(day_key, "%Y-%m-%d").date()
        day_label       = day_date.strftime("%A, %d/%m/%Y")

        print(f"{'=' * 60}")
        print(f"📆 {day_label}")
        print(f"{'=' * 60}")

        for wl in worklogs_do_dia:
            issue_key, summary = src_get_issue_summary(wl["issueId"])
            comment            = extract_comment(wl.get("comment"))
            time_seconds       = wl.get("timeSpentSeconds", 0)
            started_str        = wl["started"]

            target_issue = map_to_target_issue(comment, summary)

            if not target_issue:
                print(f"   ❌ [{issue_key}] {summary}")
                print(f"      Nenhuma categoria identificada para o comentário: \"{comment}\". Pulando.")
                print()
                continue

            description = clean_brackets(summary) or comment or summary

            if dst_worklog_exists(target_issue, started_str, time_seconds, description, DST_ACCOUNT_ID):
                print(f"   ⚠️  [{issue_key}] Já existe no destino (mesmo horário/texto). Pulando.")
                continue

            print(f"   🔹 [{issue_key}] {summary}")
            print(f"      ↳  Destino : [{target_issue}]")
            print(f"      ↳  Descrição: {description}")
            print(f"      ↳  Horas   : {seconds_to_hm(time_seconds)}")

            r = dst_post_worklog(target_issue, started_str, time_seconds, description)
            if r.ok:
                print(f"      ✅ Registrado com sucesso.")
            else:
                print(f"      ❌ Erro ao registrar: {r.status_code} - {r.text}")
            print()

    print("✅ Sincronização concluída.")


if __name__ == "__main__":
    main()
