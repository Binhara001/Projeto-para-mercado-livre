from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

app = Flask(__name__, static_folder='../frontend/static', static_url_path='/static')
CORS(app)


# ── Configurações ─────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("ML_CLIENT_ID", "SEU_CLIENT_ID")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "SEU_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("ML_REDIRECT_URI", "http://localhost:5000/auth/callback")
TOKEN_FILE    = "tokens.json"
BASE_URL      = "https://api.mercadolibre.com"

# ── Helpers de token ──────────────────────────────────────────────────────────
def save_tokens(data: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

def load_tokens() -> dict | None:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None

def refresh_access_token(refresh_token: str) -> dict | None:
    r = requests.post(f"{BASE_URL}/oauth/token", data={
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    })
    if r.ok:
        tokens = r.json()
        save_tokens(tokens)
        return tokens
    return None

def get_valid_token() -> str | None:
    tokens = load_tokens()
    if not tokens:
        return None
    # Tenta usar — se der 401, renova
    return tokens.get("access_token")

def ml_get(path: str, params: dict = None) -> dict | None:
    """GET autenticado na API do ML com auto-refresh."""
    tokens = load_tokens()
    if not tokens:
        return None

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params or {})

    if r.status_code == 401:
        new_tokens = refresh_access_token(tokens.get("refresh_token", ""))
        if not new_tokens:
            return None
        headers["Authorization"] = f"Bearer {new_tokens['access_token']}"
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params or {})

    return r.json() if r.ok else None

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'index.html'), 'r', encoding='utf-8') as f:
        return f.read()

@app.route("/auth/login")
def auth_login():
    url = (
        f"https://auth.mercadolivre.com.br/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return jsonify({"auth_url": url})

@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "Erro: código não recebido.", 400

    r = requests.post(f"{BASE_URL}/oauth/token", data={
        "grant_type":    "authorization_code",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "redirect_uri":  REDIRECT_URI,
    })

    if not r.ok:
        return f"Erro ao obter token: {r.text}", 400

    save_tokens(r.json())
    return """
    <html><body style="font-family:sans-serif;text-align:center;padding:60px">
      <h2>✅ Conta autorizada com sucesso!</h2>
      <p>Pode fechar esta aba e voltar ao dashboard.</p>
      <script>setTimeout(()=>window.close(),2000)</script>
    </body></html>
    """

@app.route("/auth/status")
def auth_status():
    tokens = load_tokens()
    if not tokens:
        return jsonify({"authenticated": False})
    user = ml_get(f"/users/me")
    if not user:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "user": {
            "id":       user.get("id"),
            "nickname": user.get("nickname"),
            "email":    user.get("email"),
        }
    })

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/api/dashboard")
def dashboard():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    # Padrão: hoje
    if not date_from:
        date_from = datetime.now().strftime("%Y-%m-%dT00:00:00.000-03:00")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%dT23:59:59.000-03:00")

    user_data = ml_get("/users/me")
    if not user_data:
        return jsonify({"error": "Não autenticado"}), 401

    seller_id = user_data["id"]

    # Busca pedidos no período
    orders_data = ml_get("/orders/search", {
        "seller": seller_id,
        "order.date_created.from": date_from,
        "order.date_created.to":   date_to,
        "sort":   "date_desc",
        "limit":  50,
    })

    if not orders_data:
        return jsonify({"error": "Erro ao buscar pedidos"}), 500

    orders = orders_data.get("results", [])
    total  = orders_data.get("paging", {}).get("total", 0)

    # Agrega métricas
    total_revenue   = 0.0
    total_shipping  = 0.0
    paid_orders     = 0
    pending_orders  = 0
    cancelled_orders= 0
    items_sold      = 0
    order_list      = []

    for o in orders:
        status = o.get("status", "")
        if status == "cancelled":
            cancelled_orders += 1
            continue

        total_amount    = o.get("total_amount", 0) or 0
        shipping_cost   = 0

        # Tenta pegar custo de frete do shipment
        shipment = o.get("shipping") or {}
        ship_id  = shipment.get("id")
        if ship_id:
            ship_data = ml_get(f"/shipments/{ship_id}")
            if ship_data:
                base_cost = ship_data.get("base_cost") or 0
                shipping_cost = float(base_cost)

        if status == "paid":
            paid_orders    += 1
            total_revenue  += total_amount
            total_shipping += shipping_cost
        elif status in ("confirmed", "payment_required", "payment_in_process"):
            pending_orders += 1

        # Itens do pedido
        for item in o.get("order_items", []):
            items_sold += item.get("quantity", 0)

        order_list.append({
            "id":            o.get("id"),
            "date":          o.get("date_created", "")[:10],
            "status":        status,
            "buyer":         (o.get("buyer") or {}).get("nickname", "—"),
            "item":          (o.get("order_items") or [{}])[0].get("item", {}).get("title", "—"),
            "quantity":      sum(i.get("quantity", 0) for i in o.get("order_items", [])),
            "total":         total_amount,
            "shipping_cost": shipping_cost,
        })

    return jsonify({
        "summary": {
            "total_orders":    total,
            "paid_orders":     paid_orders,
            "pending_orders":  pending_orders,
            "cancelled_orders":cancelled_orders,
            "items_sold":      items_sold,
            "total_revenue":   round(total_revenue, 2),
            "total_shipping":  round(total_shipping, 2),
            "net_revenue":     round(total_revenue - total_shipping, 2),
        },
        "orders": order_list,
        "period": {"from": date_from[:10], "to": date_to[:10]},
    })

# ── Exportar Excel ────────────────────────────────────────────────────────────
@app.route("/api/export/excel")
def export_excel():
    date_from = request.args.get("date_from", datetime.now().strftime("%Y-%m-%dT00:00:00.000-03:00"))
    date_to   = request.args.get("date_to",   datetime.now().strftime("%Y-%m-%dT23:59:59.000-03:00"))

    # Reutiliza a lógica do dashboard
    with app.test_request_context(f"/api/dashboard?date_from={date_from}&date_to={date_to}"):
        resp = dashboard()
        data = resp.get_json() if hasattr(resp, "get_json") else json.loads(resp[0].data)

    if "error" in data:
        return jsonify(data), 401

    wb = Workbook()

    # ── Aba Resumo ────────────────────────────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Resumo"

    yellow  = PatternFill("solid", fgColor="FFD700")
    green   = PatternFill("solid", fgColor="1E8449")
    dark    = PatternFill("solid", fgColor="1A1A2E")
    white_f = Font(color="FFFFFF", bold=True, size=12)
    black_f = Font(bold=True, size=11)

    ws_sum.merge_cells("A1:D1")
    ws_sum["A1"] = f"📊 Relatório Mercado Livre — {data['period']['from']} a {data['period']['to']}"
    ws_sum["A1"].font    = Font(bold=True, size=14, color="FFFFFF")
    ws_sum["A1"].fill    = dark
    ws_sum["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_sum.row_dimensions[1].height = 36

    headers = ["Métrica", "Valor"]
    ws_sum.append([])
    ws_sum.append(headers)
    for col, h in enumerate(headers, 1):
        cell = ws_sum.cell(row=3, column=col, value=h)
        cell.font = white_f
        cell.fill = green
        cell.alignment = Alignment(horizontal="center")

    s = data["summary"]
    rows = [
        ("Total de Pedidos",        s["total_orders"]),
        ("Pedidos Pagos",           s["paid_orders"]),
        ("Pedidos Pendentes",       s["pending_orders"]),
        ("Pedidos Cancelados",      s["cancelled_orders"]),
        ("Itens Vendidos",          s["items_sold"]),
        ("Faturamento Bruto",       f"R$ {s['total_revenue']:,.2f}"),
        ("Total Frete",             f"R$ {s['total_shipping']:,.2f}"),
        ("Faturamento Líquido",     f"R$ {s['net_revenue']:,.2f}"),
    ]
    for r in rows:
        ws_sum.append(list(r))

    ws_sum.column_dimensions["A"].width = 28
    ws_sum.column_dimensions["B"].width = 22

    # ── Aba Pedidos ───────────────────────────────────────────────────────────
    ws_ord = wb.create_sheet("Pedidos")
    ord_headers = ["ID Pedido", "Data", "Status", "Comprador", "Produto", "Qtd", "Total (R$)", "Frete (R$)"]
    ws_ord.append(ord_headers)
    for col, h in enumerate(ord_headers, 1):
        cell = ws_ord.cell(row=1, column=col, value=h)
        cell.font = white_f
        cell.fill = dark
        cell.alignment = Alignment(horizontal="center")

    STATUS_PT = {
        "paid": "Pago", "confirmed": "Confirmado",
        "payment_required": "Aguard. Pagamento",
        "payment_in_process": "Pagamento em processamento",
        "cancelled": "Cancelado",
    }
    light = PatternFill("solid", fgColor="F2F2F2")
    for i, o in enumerate(data["orders"]):
        row = [
            o["id"], o["date"],
            STATUS_PT.get(o["status"], o["status"]),
            o["buyer"], o["item"],
            o["quantity"], o["total"], o["shipping_cost"],
        ]
        ws_ord.append(row)
        if i % 2 == 1:
            for col in range(1, 9):
                ws_ord.cell(row=i+2, column=col).fill = light

    for col in range(1, 9):
        ws_ord.column_dimensions[get_column_letter(col)].width = 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"relatorio_ml_{data['period']['from']}_{data['period']['to']}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
 #import os
#port = int(os.environ.get("PORT",5000))
#app.run(host="0.0.0.0",port=port, debug=False)