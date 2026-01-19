from flask import Flask, render_template, abort
from flask_sqlalchemy import SQLAlchemy
import requests

app = Flask(__name__)

# Match ml.sql (adjust password if needed)
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@127.0.0.1:3306/ml"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Companies(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.String(255), primary_key=True)  # ticker
    company_logo = db.Column(db.String(255))
    company_name = db.Column(db.String(255))
    chart_link = db.Column(db.String(255))
    about_company = db.Column(db.Text)
    website = db.Column(db.String(255))
    nse_profile = db.Column(db.String(255))
    bse_profile = db.Column(db.String(255))
    face_value = db.Column(db.Integer)
    book_value = db.Column(db.Integer)
    roce_percentage = db.Column(db.Numeric(12, 2))
    roe_percentage = db.Column(db.Numeric(12, 2))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/companies")
def all_companies():
    companies = Companies.query.order_by(Companies.id).all()

    company_cards = []
    for c in companies:
        roe = float(c.roe_percentage or 0)
        roce = float(c.roce_percentage or 0)

        is_exclusive = roe >= 20 and roce >= 20

        company_cards.append(
            {
                "id": c.id,
                "name": c.company_name or c.id,
                "roe": f"{roe:.1f}%" if c.roe_percentage is not None else "N/A",
                "roce": f"{roce:.1f}%" if c.roce_percentage is not None else "N/A",
                "is_exclusive": is_exclusive,
                "logo": c.company_logo,
            }
        )

    return render_template("all_companies.html", company_cards=company_cards)


def fetch_company_from_api(company_id: str):
    """Fetch full data for a company from Bluemutualfund API."""
    api_url = (
        "https://bluemutualfund.in/server/api/company.php"
        f"?id={company_id}&api_key=ghfkffu6378382826hhdjgk"
    )
    resp = requests.get(api_url, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.json()


@app.route("/company/<company_id>")
def company_detail(company_id):
    # Get base company info from MySQL (for list & safety)
    base_company = Companies.query.filter_by(id=company_id).first()
    if not base_company:
        abort(404)

    # Fetch full details from external API
    payload = fetch_company_from_api(company_id)
    if not payload or "company" not in payload or "data" not in payload:
        abort(404)

    api_company = payload["company"]
    api_data = payload["data"]

    # Merge DB company + API company (API overrides when present)
    class CompanyObj:
        pass

    company = CompanyObj()
    company.id = company_id
    company.company_logo = api_company.get("company_logo") or base_company.company_logo
    company.company_name = api_company.get("company_name") or base_company.company_name
    company.about_company = api_company.get("about_company") or base_company.about_company
    company.website = api_company.get("website") or base_company.website
    company.nse_profile = api_company.get("nse_profile") or base_company.nse_profile
    company.bse_profile = api_company.get("bse_profile") or base_company.bse_profile
    company.face_value = api_company.get("face_value") or base_company.face_value
    company.book_value = api_company.get("book_value") or base_company.book_value
    company.roce_percentage = api_company.get("roce_percentage") or base_company.roce_percentage
    company.roe_percentage = api_company.get("roe_percentage") or base_company.roe_percentage

    # TradingView chart always from NSE symbol
    base_tv = "https://in.tradingview.com/chart/?symbol=NSE:"
    company.chart_link = base_tv + company_id

    # Metrics – use first analysis entry if present
    analysis_list = api_data.get("analysis", [])
    if analysis_list:
        a0 = analysis_list[0]
        metrics = {
            "roe": a0.get("roe", "N/A"),
            "sales_cagr": a0.get("compounded_sales_growth", "N/A"),
            "profit_cagr": a0.get("compounded_profit_growth", "N/A"),
        }
    else:
        metrics = {"roe": "N/A", "sales_cagr": "N/A", "profit_cagr": "N/A"}

    # Pros & cons
    pros_list = []
    cons_list = []
    for pc in api_data.get("prosandcons", []):
        if pc.get("pros") and pc["pros"] != "NULL":
            pros_list.append(pc["pros"])
        if pc.get("cons") and pc["cons"] != "NULL":
            cons_list.append(pc["cons"])

    balancesheet = api_data.get("balancesheet", [])
    profitandloss = api_data.get("profitandloss", [])
    cashflow = api_data.get("cashflow", [])
    documents = api_data.get("documents", [])

    # Exclusive rule from ROE & ROCE
    try:
        roe_val = float(company.roe_percentage or 0)
    except ValueError:
        roe_val = 0.0
    try:
        roce_val = float(company.roce_percentage or 0)
    except ValueError:
        roce_val = 0.0
    is_exclusive = roe_val >= 20 and roce_val >= 20

    return render_template(
        "company_detail.html",
        company_id=company_id,
        company=company,
        metrics=metrics,
        pros_list=pros_list,
        cons_list=cons_list,
        balancesheet=balancesheet,
        profitandloss=profitandloss,
        cashflow=cashflow,
        documents=documents,
        is_exclusive=is_exclusive,
    )


if __name__ == "__main__":
    app.run(debug=True)
