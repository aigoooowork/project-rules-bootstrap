from fastapi import APIRouter

from src.repositories.users import list_users

router = APIRouter(prefix="/users")


@router.get("")
def get_users():
    return list_users()
