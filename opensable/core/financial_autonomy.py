"""
Financial Autonomy,  WORLD FIRST
Full financial independence: invoicing, billing, fund management,
budget optimization, and autonomous resource allocation.
The agent manages its own economic survival and growth.
"""
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class FinancialAccount:
    id: str
    name: str
    account_type: str  # operating, savings, investment, revenue
    balance: float = 0.0
    currency: str = "USD"
    created_at: str = ""

@dataclass
class Transaction:
    id: str
    account_id: str
    amount: float
    transaction_type: str  # income, expense, transfer, investment
    category: str
    description: str
    timestamp: str
    status: str = "completed"  # pending, completed, failed

@dataclass
class Invoice:
    id: str
    client: str
    amount: float
    currency: str = "USD"
    description: str = ""
    issued_at: str = ""
    due_date: str = ""
    status: str = "draft"  # draft, sent, paid, overdue, cancelled

@dataclass
class Budget:
    category: str
    allocated: float
    spent: float = 0.0
    period: str = "monthly"  # daily, weekly, monthly, yearly

# ── Core Engine ───────────────────────────────────────────────────────

class FinancialAutonomy:
    """
    Autonomous financial management engine.
    Handles invoicing, budgeting, resource allocation,
    cost optimization, and economic self-sustainability.
    """

    MAX_TRANSACTIONS = 1000

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "financial_autonomy_state.json"

        self.accounts: List[FinancialAccount] = []
        self.transactions: List[Transaction] = []
        self.invoices: List[Invoice] = []
        self.budgets: List[Budget] = []
        self.total_revenue = 0.0
        self.total_expenses = 0.0
        self.total_transactions = 0

        self._load_state()

        # Create default operating account if none exist
        if not self.accounts:
            self.create_account("Operating", "operating")

    def create_account(self, name: str, account_type: str = "operating", currency: str = "USD") -> FinancialAccount:
        """Create a new financial account."""
        acc_id = hashlib.sha256(f"{name}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]
        account = FinancialAccount(
            id=acc_id, name=name, account_type=account_type,
            currency=currency, created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.accounts.append(account)
        self._save_state()
        return account

    def record_transaction(self, account_id: str, amount: float, tx_type: str,
                           category: str, description: str) -> Optional[Transaction]:
        """Record a financial transaction."""
        account = next((a for a in self.accounts if a.id == account_id), None)
        if not account:
            return None

        tx_id = hashlib.sha256(f"tx_{datetime.now().isoformat()}_{amount}".encode()).hexdigest()[:10]
        tx = Transaction(
            id=tx_id, account_id=account_id, amount=amount,
            transaction_type=tx_type, category=category,
            description=description, timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Update account balance
        if tx_type in ("income", "revenue"):
            account.balance += amount
            self.total_revenue += amount
        elif tx_type in ("expense", "cost"):
            account.balance -= amount
            self.total_expenses += amount
        elif tx_type == "investment":
            account.balance -= amount
            self.total_expenses += amount

        self.transactions.append(tx)
        self.total_transactions += 1

        # Update budget tracking
        matching_budget = next((b for b in self.budgets if b.category == category), None)
        if matching_budget and tx_type in ("expense", "cost"):
            matching_budget.spent += amount

        # Trim transactions
        if len(self.transactions) > self.MAX_TRANSACTIONS:
            self.transactions = self.transactions[-self.MAX_TRANSACTIONS:]

        self._save_state()
        return tx

    def create_invoice(self, client: str, amount: float, description: str,
                       currency: str = "USD", due_date: str = "") -> Invoice:
        """Create an invoice."""
        inv_id = hashlib.sha256(f"inv_{client}_{datetime.now().isoformat()}".encode()).hexdigest()[:10]
        invoice = Invoice(
            id=inv_id, client=client, amount=amount, currency=currency,
            description=description, issued_at=datetime.now(timezone.utc).isoformat(),
            due_date=due_date,
        )
        self.invoices.append(invoice)
        self._save_state()
        return invoice

    def mark_invoice_paid(self, invoice_id: str) -> bool:
        """Mark an invoice as paid and record the revenue."""
        invoice = next((i for i in self.invoices if i.id == invoice_id), None)
        if not invoice:
            return False

        invoice.status = "paid"
        # Record as revenue in operating account
        operating = next((a for a in self.accounts if a.account_type == "operating"), None)
        if operating:
            self.record_transaction(
                operating.id, invoice.amount, "income",
                "invoice_payment", f"Payment for invoice {invoice_id} from {invoice.client}",
            )
        self._save_state()
        return True

    def set_budget(self, category: str, allocated: float, period: str = "monthly") -> Budget:
        """Set or update a budget category."""
        existing = next((b for b in self.budgets if b.category == category), None)
        if existing:
            existing.allocated = allocated
            existing.period = period
        else:
            existing = Budget(category=category, allocated=allocated, period=period)
            self.budgets.append(existing)
        self._save_state()
        return existing

    async def optimize_costs(self, llm=None) -> Dict[str, Any]:
        """Analyze spending patterns and suggest optimizations."""
        report = {
            "total_revenue": self.total_revenue,
            "total_expenses": self.total_expenses,
            "net_balance": sum(a.balance for a in self.accounts),
            "budget_status": [],
            "recommendations": [],
        }

        # Check budget overruns
        for budget in self.budgets:
            pct = (budget.spent / budget.allocated * 100) if budget.allocated > 0 else 0
            status = "ok" if pct < 80 else ("warning" if pct < 100 else "overrun")
            report["budget_status"].append({
                "category": budget.category, "allocated": budget.allocated,
                "spent": budget.spent, "pct": round(pct, 1), "status": status,
            })

        # LLM-powered optimization recommendations
        if llm and self.transactions:
            try:
                recent_tx = self.transactions[-20:]
                tx_summary = json.dumps([{"type": t.transaction_type, "category": t.category,
                                          "amount": t.amount} for t in recent_tx])
                prompt = (
                    f"Analyze these financial transactions and provide 3 cost optimization "
                    f"recommendations. Reply as JSON array of strings.\n\n{tx_summary}"
                )
                analysis = await llm.chat_raw(prompt, max_tokens=300)
                try:
                    recs = json.loads(analysis.strip())
                    if isinstance(recs, list):
                        report["recommendations"] = recs[:5]
                except json.JSONDecodeError:
                    report["recommendations"] = [analysis.strip()[:200]]
            except Exception as e:
                logger.debug(f"Cost optimization analysis failed: {e}")

        return report

    def get_financial_summary(self) -> Dict[str, Any]:
        """Get comprehensive financial summary."""
        total_balance = sum(a.balance for a in self.accounts)
        pending_invoices = sum(i.amount for i in self.invoices if i.status in ("draft", "sent"))
        return {
            "total_balance": round(total_balance, 2),
            "total_revenue": round(self.total_revenue, 2),
            "total_expenses": round(self.total_expenses, 2),
            "net_profit": round(self.total_revenue - self.total_expenses, 2),
            "pending_invoices": round(pending_invoices, 2),
            "accounts_count": len(self.accounts),
            "active_budgets": len(self.budgets),
        }

    def get_stats(self) -> Dict[str, Any]:
        total_balance = sum(a.balance for a in self.accounts)
        return {
            "total_balance": round(total_balance, 2),
            "total_revenue": round(self.total_revenue, 2),
            "total_expenses": round(self.total_expenses, 2),
            "net_profit": round(self.total_revenue - self.total_expenses, 2),
            "total_transactions": self.total_transactions,
            "accounts": len(self.accounts),
            "active_invoices": sum(1 for i in self.invoices if i.status in ("draft", "sent")),
            "budget_categories": len(self.budgets),
        }

    def _save_state(self):
        try:
            state = {
                "accounts": [asdict(a) for a in self.accounts],
                "transactions": [asdict(t) for t in self.transactions[-200:]],
                "invoices": [asdict(i) for i in self.invoices],
                "budgets": [asdict(b) for b in self.budgets],
                "total_revenue": self.total_revenue,
                "total_expenses": self.total_expenses,
                "total_transactions": self.total_transactions,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"FinancialAutonomy save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.accounts = [FinancialAccount(**a) for a in state.get("accounts", [])]
                self.transactions = [Transaction(**t) for t in state.get("transactions", [])]
                self.invoices = [Invoice(**i) for i in state.get("invoices", [])]
                self.budgets = [Budget(**b) for b in state.get("budgets", [])]
                self.total_revenue = state.get("total_revenue", 0.0)
                self.total_expenses = state.get("total_expenses", 0.0)
                self.total_transactions = state.get("total_transactions", 0)
        except Exception as e:
            logger.debug(f"FinancialAutonomy load failed: {e}")
