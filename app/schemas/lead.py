from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


class LeadCreate(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre completo del lead")
    correo: EmailStr = Field(..., description="Correo electrónico válido")
    telefono: Optional[str] = Field(None, description="Número de teléfono")
    intereses_servicios: List[str] = Field(
        ..., description="Lista de servicios de interés"
    )
    mensaje: Optional[str] = Field(None, description="Mensaje adicional del lead")


class LeadResponse(BaseModel):
    id: int
    nombre: str
    correo: EmailStr
    telefono: Optional[str]
    intereses_servicios: List[str]
    mensaje: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
