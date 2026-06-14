# 🚆 TransitIQ

> **AI-powered railway route planning platform for intelligent journey discovery.**

TransitIQ is a modern railway route planning application that leverages GTFS timetable data to help users discover optimal train journeys, including complex multi-transfer routes. 

## 🧐 The Problem & Our Solution

**The Problem:** Traditional railway apps are static and rigid. They act as simple database search tools, making it incredibly difficult for users to discover hidden multi-transfer routes or get personalized guidance for their journeys.

**The Solution:** TransitIQ introduces **AI Integration** into the core of railway planning. While other apps leave you to figure out complex transfers on your own, TransitIQ uses an AI Journey Assistant combined with intelligent routing algorithms to not only find the best routes (direct, 1-transfer, and 2-transfer) but to actively guide you through your itinerary.

## ✨ Key Features

* 🤖 **AI Journey Assistant:** Context-aware travel recommendations, natural language summaries, and dynamic trip guidance.
* 🛤️ **Smart Multi-Transfer Routing:** Instantly discover the best way to travel with validated 1-transfer and 2-transfer algorithms.
* 🗺️ **Interactive Journey Maps:** Visual representation of routes, stops, and transfer nodes using React-Leaflet.
* ⏱️ **Station-by-Station Roadmap:** A detailed timeline detailing departure times, arrival times, and layover durations.
* 🚀 **High-Performance GTFS Engine:** Fast, scalable processing of massive General Transit Feed Specification datasets.

## 🏛️ Architecture

TransitIQ uses a decoupled client-server architecture deployed on Microsoft Azure.

```mermaid
graph TD
    Client[Client Browser] -->|HTTPS| ASWA[Azure Static Web Apps]
    ASWA -->|REST API| API Gateway[Azure App Service]
    API Gateway --> FlaskBackend[Python Flask API]
    FlaskBackend --> RoutingEngine[Routing & Transfer Algorithms]
    FlaskBackend --> GTFSData[(GTFS Indexed Data)]
    FlaskBackend --> AILayer[Azure AI Integration]
```

## 📸 Screenshots

| Home & Search | Route Results |
|:---:|:---:|
| ![Home Page](https://via.placeholder.com/400x250.png?text=Home+Page+&+Search) | ![Search Results](https://via.placeholder.com/400x250.png?text=Search+Results) |

| Interactive Map | AI Journey Assistant |
|:---:|:---:|
| ![Interactive Map](https://via.placeholder.com/400x250.png?text=Interactive+Map) | ![Journey Roadmap](https://via.placeholder.com/400x250.png?text=AI+Journey+Assistant) |

## 🛠️ Technology Stack

* **Frontend:** React, TypeScript, Vite, React-Leaflet
* **Backend:** Python, Flask, Gunicorn
* **Data:** GTFS (General Transit Feed Specification)
* **Cloud & AI:** Microsoft Azure (App Service, Static Web Apps, Azure AI)

## 🚀 Installation & Setup

### Prerequisites
* Node.js (v18+)
* Python (3.9+)

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/TransitIQ.git
cd TransitIQ
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend` folder:
```env
PORT=5000
CORS_ORIGIN=http://localhost:5173
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

Start the backend:
```bash
flask run --port=5000
```

### 3. Frontend Setup
Open a new terminal window:
```bash
cd frontend
npm install
```

Create a `.env` file in the `frontend` folder:
```env
VITE_API_BASE_URL=http://localhost:5000/api
```

Start the frontend:
```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check [issues page](https://github.com/yourusername/TransitIQ/issues).

## 📝 License

This project is [MIT](LICENSE) licensed.
