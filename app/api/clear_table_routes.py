from fastapi import APIRouter, HTTPException, Depends, status
from app.dependencies.depends import get_db
from pymongo.database import Database
from pymongo.errors import PyMongoError


async def clear_entries(table_name: str, db: Database):
    users_collection = db[table_name]
    await users_collection.delete_many({}) # Assuming asynchronous MongoDB driver
    return True  # Return a boolean or None for consistency


router = APIRouter(tags=['CLEAR COLLECTIONS'])

@router.post("/clear_tables", status_code=status.HTTP_200_OK)
async def clear_tables(table_name: str = "conversations", db: Database = Depends(get_db)):  # Add Authentication
    try:
        await clear_entries(table_name, db)
        return {"status": 200, "message": "Table cleared successfully"}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")