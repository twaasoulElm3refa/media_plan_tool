from openai import OpenAI
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from database import get_db_connection , get_data_by_request_id , update_editor_result 

