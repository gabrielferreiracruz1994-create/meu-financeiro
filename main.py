import os
import sys
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://usuario:senha@host:5432/postgres")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProfileModel(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

class CardModel(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    total_limit = Column(Float, nullable=False)
    closing_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)

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
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=True)

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ProfileCreate(BaseModel):
    name: str

class CardCreate(BaseModel):
    name: str
    entity: str
    total_limit: float
    closing_day: int
    due_day: int

class CardUpdate(BaseModel):
    name: str
    entity: str
    total_limit: float
    closing_day: int
    due_day: int

class BillCreate(BaseModel):
    group_id: Optional[str] = None
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

class BillUpdateScope(BaseModel):
    creditor: str
    entity: str
    installment_amount: float
    due_date: str
    scope: str # 'THIS', 'THIS_AND_FUTURE', 'ALL'

# ROTAS DE PERFIS
@app.get("/api/profiles")
def get_profiles(db: Session = Depends(get_db)):
    return db.query(ProfileModel).all()

@app.post("/api/profiles")
def create_profile(profile: ProfileCreate, db: Session = Depends(get_db)):
    existing = db.query(ProfileModel).filter(ProfileModel.name == profile.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Perfil já existe")
    db_profile = ProfileModel(name=profile.name)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
    if profile:
        db.delete(profile)
        db.commit()
        return {"message": "Perfil excluído com sucesso"}
    raise HTTPException(status_code=404, detail="Perfil não encontrado")

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

@app.put("/api/cards/{card_id}")
def update_card(card_id: int, card_data: CardUpdate, db: Session = Depends(get_db)):
    card = db.query(CardModel).filter(CardModel.id == card_id).first()
    if card:
        card.name = card_data.name
        card.entity = card_data.entity
        card.total_limit = card_data.total_limit
        card.closing_day = card_data.closing_day
        card.due_day = card_data.due_day
        db.commit()
        db.refresh(card)
        return card
    raise HTTPException(status_code=404, detail="Cartão não encontrado")

@app.delete("/api/cards/{card_id}")
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CardModel).filter(CardModel.id == card_id).first()
    if card:
        db.query(BillModel).filter(BillModel.card_id == card_id).delete()
        db.delete(card)
        db.commit()
        return {"message": "Cartão e lançamentos associados excluídos com sucesso"}
    raise HTTPException(status_code=404, detail="Cartão não encontrado")

# ROTAS DE DÍVIDAS
@app.get("/api/bills")
def get_bills(db: Session = Depends(get_db)):
    return db.query(BillModel).all()

@app.post("/api/bills/batch")
def create_bills_batch(bills_list: List[BillCreate], db: Session = Depends(get_db)):
    group_uuid = str(uuid.uuid4()) if len(bills_list) > 1 else None
    db_objs = []
    for b in bills_list:
        data = b.dict()
        if len(bills_list) > 1:
            data["group_id"] = group_uuid
        db_objs.append(BillModel(**data))
    
    db.add_all(db_objs)
    db.commit()
    return {"message": f"{len(db_objs)} lançamentos criados com sucesso"}

@app.put("/api/bills/{bill_id}/scoped")
def update_bill_scoped(bill_id: int, data: BillUpdateScope, db: Session = Depends(get_db)):
    target = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Dívida não encontrada")

    if not target.group_id or data.scope == 'THIS':
        target.creditor = data.creditor
        target.entity = data.entity
        target.installment_amount = data.installment_amount
        target.due_date = data.due_date
    elif data.scope == 'ALL':
        related = db.query(BillModel).filter(BillModel.group_id == target.group_id).all()
        for b in related:
            b.creditor = data.creditor
            b.entity = data.entity
            b.installment_amount = data.installment_amount
    elif data.scope == 'THIS_AND_FUTURE':
        related = db.query(BillModel).filter(
            BillModel.group_id == target.group_id,
            BillModel.installment_number >= target.installment_number
        ).all()
        for b in related:
            b.creditor = data.creditor
            b.entity = data.entity
            b.installment_amount = data.installment_amount

    db.commit()
    return {"message": "Atualização concluída com sucesso"}

@app.delete("/api/bills/{bill_id}/scoped")
def delete_bill_scoped(bill_id: int, scope: str = 'THIS', db: Session = Depends(get_db)):
    target = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Dívida não encontrada")

    if not target.group_id or scope == 'THIS':
        db.delete(target)
    elif scope == 'ALL':
        db.query(BillModel).filter(BillModel.group_id == target.group_id).delete()
    elif scope == 'THIS_AND_FUTURE':
        db.query(BillModel).filter(
            BillModel.group_id == target.group_id,
            BillModel.installment_number >= target.installment_number
        ).delete()

    db.commit()
    return {"message": "Exclusão concluída com sucesso"}

@app.put("/api/bills/{bill_id}/status")
def update_bill_status(bill_id: int, status_data: dict, db: Session = Depends(get_db)):
    bill = db.query(BillModel).filter(BillModel.id == bill_id).first()
    if bill:
        bill.is_paid = status_data.get("is_paid", False)
        db.commit()
        return {"message": "Status atualizado"}
    raise HTTPException(status_code=404, detail="Dívida não encontrada")

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
