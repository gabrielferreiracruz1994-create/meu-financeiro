import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Pega o link do banco do Supabase via variável de ambiente ou usa o link direto
DATABASE_URL = os.getenv("DATABASE_URL", "COLE_AQUI_A_SUA_CONNECTION_STRING_DO_SUPABASE")

# Correção caso o link comece com 'postgres://' (SQLAlchemy exige 'postgresql://')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MODELO DO BANCO DE DADOS
class BillModel(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(String, nullable=True)
    creditor = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    installment_number = Column(Integer, nullable=False)
    total_installments = Column(Integer, nullable=False)
    installment_amount = Column(Float, nullable=False)
    due_date = Column(String, nullable=False)
    is_paid = Column(Boolean, default=False)
    is_recurrent = Column(Boolean, default=False)
    created_by_user = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if os.path.exists("templates"):
    app.mount("/static", StaticFiles(directory="templates"), name="static")

@app.get("/")
def read_root():
    if os.path.exists("templates/index.html"):
        return FileResponse("templates/index.html")
    return {"message": "Servidor funcionando! A interface está em templates/index.html"}

# ROTAS DA API PARA SALVAR E CONSULTAR DADOS PERMANENTES

class BillCreate(BaseModel):
    creditor: str
    entity: str
    total_amount: float
    installment_number: int
    total_installments: int
    installment_amount: float
    due_date: str
    is_recurrent: bool
    created_by_user: str

@app.get("/api/bills")
def get_bills(db: Session = Depends(get_db)):
    bills = db.query(BillModel).all()
    return bills

@app.post("/api/bills")
def create_bill(bill: BillCreate, db: Session = Depends(get_db)):
    db_bill = BillModel(**bill.dict())
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

@app.delete("/api/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if bill:
        db.delete(bill)
        db.commit()
        return {"message": "Excluído com sucesso"}
    raise HTTPException(status_code=404, detail="Não encontrado")
