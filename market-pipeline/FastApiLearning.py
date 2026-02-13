from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}


item = []

@app.post("/items/")
def create_item(name: str, price: float):
    item.append({"name": name, "price": price})
    return item

@app.get("/items/")
def read_items():
    return item