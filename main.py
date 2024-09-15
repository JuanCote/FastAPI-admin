from datetime import date
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Query, Request
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, Transaction, User


app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Initialize the database
Base.metadata.create_all(bind=engine)

app = FastAPI()


class UserUpdate(BaseModel):
    new_username: str


class TransactionUpdate(BaseModel):
    new_transaction_type: Optional[str] = None
    new_amount: Optional[float] = None


# Dependency for obtaining a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Add a new user
@app.post("/add_user")
def add_user(username: str, db: Session = Depends(get_db)):
    user = User(username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user_id": user.id}


# Retrieve information about a specific user
@app.get("/get_user/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    return {
        "id": user.id,
        "username": user.username,
        "transactions": [
            {"transaction_type": t.transaction_type, "amount": t.amount}
            for t in transactions
        ],
    }


# Retrieve information about all users
@app.get("/get_all_users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    result = []
    for user in users:
        transactions = (
            db.query(Transaction).filter(Transaction.user_id == user.id).all()
        )
        user_data = {
            "id": user.id,
            "username": user.username,
            "transactions": [
                {"transaction_type": t.transaction_type, "amount": t.amount}
                for t in transactions
            ],
        }
        result.append(user_data)
    return result


# Add a new transaction
@app.post("/add_transaction")
def add_transaction(
    user_id: int, transaction_type: str, amount: float, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    transaction = Transaction(
        user_id=user_id, transaction_type=transaction_type, amount=amount
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return {"transaction_id": transaction.id}


# Update user information
@app.put("/edit_user/{user_id}")
def edit_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.username = user_update.new_username
    db.commit()
    db.refresh(user)
    return {
        "message": "User updated",
        "user": {"id": user.id, "username": user.username},
    }


# Delete a user
@app.delete("/delete_user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


# Update a transaction
@app.put("/edit_transaction/{transaction_id}")
def edit_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction_update.new_transaction_type is not None:
        transaction.transaction_type = transaction_update.new_transaction_type
    if transaction_update.new_amount is not None:
        transaction.amount = transaction_update.new_amount

    db.commit()
    db.refresh(transaction)

    return {
        "message": "Transaction updated",
        "transaction": {
            "id": transaction.id,
            "transaction_type": transaction.transaction_type,
            "amount": transaction.amount,
        },
    }


# Delete a transaction
@app.delete("/delete_transaction/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(transaction)
    db.commit()
    return {"message": "Transaction deleted"}


# Admin dashboard to view transactions within a date range
@app.get("/admin")
def admin_dashboard(
    request: Request,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()

    query = db.query(Transaction)
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(Transaction.created_at <= end_date)

    query = query.order_by(asc(Transaction.created_at))

    transactions = query.all()

    total_transactions = len(transactions)
    total_amount = sum(t.amount for t in transactions)

    start_date_str = start_date.isoformat() if start_date else ""
    end_date_str = end_date.isoformat() if end_date else ""

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "users": users,
            "transactions": transactions,
            "total_transactions": total_transactions,
            "total_amount": total_amount,
            "start_date": start_date_str,
            "end_date": end_date_str,
        },
    )
