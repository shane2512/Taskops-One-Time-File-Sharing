DB_USER = "root"  
DB_PASSWORD = ""  
DB_HOST = "localhost"  
DB_PORT = "3306"  
DB_NAME = "file_sharing"  

SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"  
SQLALCHEMY_TRACK_MODIFICATIONS = False  
UPLOAD_FOLDER = "backend/uploads"  
