import gspread
from google.oauth2.service_account import Credentials
from typing import Optional
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class GoogleSheetsExporter:
    def __init__(self, creds_path: Optional[str] = None):
        self.creds_path = creds_path or os.getenv("GOOGLE_CREDS_PATH")
        self.spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
        self.client = None
        self.sheet = None

    def connect(self):
        """Connect to Google Sheets"""
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(
            self.creds_path, scopes=scopes
        )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(self.spreadsheet_id)

    def add_listing(self, listing: dict, sheet_name: str = "Объекты"):
        """Add listing to sheet"""
        if not self.sheet:
            self.connect()

        worksheet = self.sheet.worksheet(sheet_name)
        
        # Get next ID
        all_values = worksheet.get_all_values()
        next_id = len(all_values)

        # Prepare row
        row = [
            str(next_id),  # ID
            datetime.now().strftime("%d.%m.%Y"),  # Дата
            listing.get("source", ""),  # Источник
            listing.get("link", ""),  # Ссылка
            listing.get("address", ""),  # Адрес
            listing.get("district", ""),  # Район
            str(listing.get("area", 0)),  # Площадь
            f"{listing.get('floor', 0)}/{listing.get('total_floors', 0)}",  # Этаж
            listing.get("fund_type", ""),  # Фонд
            listing.get("renovation", ""),  # Ремонт
            listing.get("has_parking", ""),  # Парковка
            listing.get("seller_type", ""),  # Продавец
            str(listing.get("price", 0)),  # Цена
            str(listing.get("price_per_m2", 0)),  # Цена за м²
            "Новый",  # Статус
            ""  # Комментарий М.А.
        ]

        worksheet.append_row(row)
        return next_id

    def check_exists(self, external_id: str, sheet_name: str = "Объекты") -> bool:
        """Check if listing already exists"""
        if not self.sheet:
            self.connect()

        worksheet = self.sheet.worksheet(sheet_name)
        links = worksheet.col_values(4)  # Column D - links
        
        for link in links:
            if external_id in link:
                return True
        return False


# Instance for direct use
exporter = GoogleSheetsExporter()
