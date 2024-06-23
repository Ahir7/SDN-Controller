# This implements the IBN API endpoints. The POST endpoint writes the
# [cite_start]declarative intent to the PostgreSQL database[cite: 163, 167].

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models
import uuid
from typing import List

app = FastAPI(
    title="SDN Zero-Trust IBN API",
    description="API for managing declarative security policies."
)


# Dependency to get DB session
def get_db():
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/api/v1/policies", response_model=models.PolicyResponse, status_code=201)
def create_policy(policy: models.PolicySchema, db: Session = Depends(get_db)):
    """
    Create a new declarative security policy.
    This intent is written to the PostgreSQL database[cite: 62].
    """
    policy_id = str(uuid.uuid4())
    db_policy = models.PolicyDB(
        id=policy_id,
        name=policy.name,
        priority=policy.priority,
        source=policy.source.dict(),
        destination=policy.destination.dict(),
        service=[s.dict() for s in policy.service] if policy.service else None,
        action=policy.action,
        status=policy.status
    )
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy


@app.get("/api/v1/policies", response_model=List[models.PolicyResponse])
def get_all_policies(db: Session = Depends(get_db)):
    """
    Retrieve all active policies from the database.
    The Master Ryu controller will use a similar function[cite: 64].
    """
    policies = db.query(models.PolicyDB).all()
    return policies


@app.get("/api/v1/policies/{policy_id}", response_model=models.PolicyResponse)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific policy by ID.
    """
    policy = db.query(models.PolicyDB).filter(models.PolicyDB.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.put("/api/v1/policies/{policy_id}", response_model=models.PolicyResponse)
def update_policy(policy_id: str, policy: models.PolicySchema, db: Session = Depends(get_db)):
    """
    Update an existing policy.
    The Ryu controller will detect this change via its polling mechanism.
    """
    db_policy = db.query(models.PolicyDB).filter(models.PolicyDB.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Update fields
    db_policy.name = policy.name
    db_policy.priority = policy.priority
    db_policy.source = policy.source.dict()
    db_policy.destination = policy.destination.dict()
    db_policy.service = [s.dict() for s in policy.service] if policy.service else None
    db_policy.action = policy.action
    db_policy.status = policy.status
    
    db.commit()
    db.refresh(db_policy)
    return db_policy


@app.delete("/api/v1/policies/{policy_id}", status_code=204)
def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    """
    Delete a policy by ID.
    The Ryu controller will detect this change and remove associated flows.
    """
    db_policy = db.query(models.PolicyDB).filter(models.PolicyDB.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(db_policy)
    db.commit()
    return None


