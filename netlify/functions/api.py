from mangum import Mangum

from api.main import app

handler = Mangum(app, api_gateway_base_path="/.netlify/functions/api")
