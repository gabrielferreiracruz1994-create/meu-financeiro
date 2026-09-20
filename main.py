import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Pega a URL do Supabase via variável de ambiente no Render
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:senha@host:5432/postgres")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MODELO DE CARTÕES
class CardModel(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    total_limit = Column(Float, nullable=False)
    closing_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)

# MODELO DE DÍVIDAS E PARCELAS
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
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# SCHEMAS DE VALIDAÇÃO
class CardCreate(BaseModel):
    name: str
    entity: str
    total_limit: float
    closing_day: int
    due_day: int

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
    card_id: Optional[int] = None

class BillStatusUpdate(BaseModel):
    is_paid: bool

# ROTAS DE CARTÕES
@app.get("/api/cards")
def get_cards(db: Session = Depends(get_db)):
    return db.query(CardModel).all()

@app.post("/api/cards")
def create_card(card: CardCreate, db: Session = Depends(get_db)):
    db_card = CardModel(**card.dict())
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card

@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CardModel).filter(CardModel.id == card_id).first()
    if card:
        db.delete(card)
        db.commit()
        return {"message": "Cartão excluído"}
    raise HTTPException(status_code=404, detail="Cartão não encontrado")

# ROTAS DE DÍVIDAS
@app.get("/api/bills")
def get_bills(db: Session = Depends(get_db)):
    return db.query(BillModel).all()

@app.post("/api/bills")
def create_bill(bill: BillCreate, db: Session = Depends(get_db)):
    db_bill = BillModel(**bill.dict())
    db.add(db_bill)
    db.commit()
    db.refresh(db_bill)
    return db_bill

@app.put("/api/bills/{bill_id}/status")
def update_bill_status(bill_id: int, status_data: BillStatusUpdate, db: Session = Depends(get_db)):
    bill = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if bill:
        bill.is_paid = status_data.is_paid
        db.commit()
        return {"message": "Status atualizado"}
    raise HTTPException(status_code=404, detail="Dívida não encontrada")

@app.delete("/api/bills/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if bill:
        db.delete(bill)
        db.commit()
        return {"message": "Excluído com sucesso"}
    raise HTTPException(status_code=404, detail="Não encontrado")

@app.get("/manifest.json")
def get_manifest():
    if os.path.exists("manifest.json"):
        return FileResponse("manifest.json")
    raise HTTPException(status_code=404, detail="Manifest não encontrado")

if os.path.exists("templates"):
    app.mount("/static", StaticFiles(directory="templates"), name="static")

@app.get("/")
def read_root():
    if os.path.exists("templates/index.html"):
        return FileResponse("templates/index.html")
    return {"message": "Servidor funcionando!"}
