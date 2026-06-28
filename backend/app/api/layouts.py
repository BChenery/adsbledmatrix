from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.models import Layout, LayoutElement

router = APIRouter(prefix="/api/layouts", tags=["layouts"])


class ElementCreate(BaseModel):
    element_type: str
    x: int
    y: int
    width: Optional[int] = None
    height: Optional[int] = None
    z_index: int = 0
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    color: Optional[str] = None
    bg_color: Optional[str] = None
    format_str: Optional[str] = None
    data_field: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    show_if: Optional[str] = None
    extra: Optional[dict] = None


class ElementResponse(ElementCreate):
    id: int

    class Config:
        from_attributes = True


class LayoutCreate(BaseModel):
    name: str
    description: Optional[str] = None
    width: int = 256
    height: int = 128
    is_default: bool = False
    elements: List[ElementCreate] = []


class LayoutUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_default: Optional[bool] = None


class LayoutResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    width: int
    height: int
    is_default: bool
    elements: List[ElementResponse]

    class Config:
        from_attributes = True


class LayoutListResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    width: int
    height: int
    is_default: bool

    class Config:
        from_attributes = True


@router.get("", response_model=List[LayoutListResponse])
async def list_layouts(session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Layout).options(selectinload(Layout.elements)))
    layouts = result.scalars().all()
    return layouts


@router.post("", response_model=LayoutResponse, status_code=201)
async def create_layout(layout: LayoutCreate, session: AsyncSession = Depends(get_db)):
    db_layout = Layout(
        name=layout.name,
        description=layout.description,
        width=layout.width,
        height=layout.height,
        is_default=layout.is_default,
    )
    session.add(db_layout)
    await session.flush()

    for elem in layout.elements:
        db_elem = LayoutElement(layout_id=db_layout.id, **elem.model_dump())
        session.add(db_elem)

    await session.commit()
    await session.refresh(db_layout)
    return db_layout


@router.get("/{layout_id}", response_model=LayoutResponse)
async def get_layout(layout_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Layout).where(Layout.id == layout_id).options(selectinload(Layout.elements)))
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


@router.put("/{layout_id}", response_model=LayoutResponse)
async def update_layout(layout_id: int, update: LayoutUpdate, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Layout).where(Layout.id == layout_id))
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(layout, field, value)

    await session.commit()
    await session.refresh(layout)
    return layout


@router.delete("/{layout_id}", status_code=204)
async def delete_layout(layout_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Layout).where(Layout.id == layout_id))
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    await session.delete(layout)
    await session.commit()


@router.post("/{layout_id}/elements", response_model=ElementResponse, status_code=201)
async def add_element(layout_id: int, element: ElementCreate, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(Layout).where(Layout.id == layout_id))
    layout = result.scalar_one_or_none()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")

    db_elem = LayoutElement(layout_id=layout_id, **element.model_dump())
    session.add(db_elem)
    await session.commit()
    await session.refresh(db_elem)
    return db_elem


@router.put("/elements/{element_id}", response_model=ElementResponse)
async def update_element(element_id: int, update: ElementCreate, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(LayoutElement).where(LayoutElement.id == element_id))
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(status_code=404, detail="Element not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(elem, field, value)

    await session.commit()
    await session.refresh(elem)
    return elem


@router.delete("/elements/{element_id}", status_code=204)
async def delete_element(element_id: int, session: AsyncSession = Depends(get_db)):
    result = await session.execute(select(LayoutElement).where(LayoutElement.id == element_id))
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(status_code=404, detail="Element not found")
    await session.delete(elem)
    await session.commit()
