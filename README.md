# Mirage

## Overview

**Mirage** offers a self-hosted and privacy-focused photo storage and management solution. It provides robust capabilities comparable to cloud-based solutions while ensuring that users maintain full control over their data.

## Architecture

Mirage is a two-part system consisting of:

- **Backend (Server)**: A Flask-based API that handles image and video processing, metadata extraction, duplicate detection, and search functionality. The backend is responsible for executing AI-driven tasks and storing processed results.
- **Frontend (Client)**: A web-based interface that allows users to interact with their media, create albums, search, tag, and manage files easily. The client connects to the backend via API requests.

Both components can be deployed using the `docker-compose.yml` file which is the recommended method of installation.

### Capabilities

- **Face Recognition**: Automatically detects and categorizes individuals in images. see #6
- **Albums**: Organize photos and videos into structured albums. see #7
- **Duplicate Detection**: Identifies and groups visually similar media. see #8
- **Metadata Extraction**: Retrieves and displays EXIF and other metadata. see #9
- **Search & Filtering**: Quickly find photos based on people, dates, locations, or tags. see #10
- **Local AI Processing**: Performs image analysis without relying on external servers.
- **Tagging & Annotations**: Users can add descriptions, keywords, and comments to media files. see #11

## Under the Hood

### **Duplicate Detection**

Mirage utilizes deep learning models to generate vector embeddings for images. These embeddings represent unique visual features, enabling Mirage to compare images efficiently and detect duplicates.

### **Metadata Extraction**

Mirage  extracts detailed metadata from images and videos, including camera settings, geolocation, timestamps, and other embedded properties. This metadata enhances searchability and allows users to organize media based on relevant attributes.

### **Security and Authentication**

Mirage's backend, built with Flask, ensures secure access to media using basic authentication and HTTPS support. see #12

### **Logging and Monitoring**

The system implements  logging for server events, ensuring that error tracking and system monitoring are efficient. Logs are stored and rotated periodically to maintain system performance.

### **Scalability with Docker**

Mirage is designed to be containerized using Docker, allowing for easy deployment and scaling. By running the backend and frontend in separate containers, users can ensure better performance and isolation of processes.

## Installation

### Recommended: Running with Docker

The preferred method for deploying Mirage is using Docker, which ensures consistency and ease of deployment.

1. Clone the repository:

   ```bash
   git clone https://github.com/hetkpatel/Mirage.git
   cd Mirage
   ```

2. Create a copy of the `example.env` file and rename it to `.env`.

   ```bash
   cp example.env .env
   ```

3. Edit the `.env` variables

4. Run the containers using Docker Compose:

   ```bash
   docker compose up -d
   ```

This will start both the backend and frontend containers, making the server accessible at `http://localhost:5000`, and the website at `http://localhost:80`.

### Alternative: Running with Python (server only)

If you prefer to run Mirage without Docker, follow these steps:

1. Clone the repository:

   ```bash
   git clone https://github.com/hetkpatel/Mirage.git
   cd Mirage
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the Flask server:

   ```bash
   python wsgi.py
   ```

This will **ONLY START** the server on `http://localhost:5000`.

## Hardware Recommendations

- At least 8GB RAM for embedding computations.
- A modern 4-core processor to handle AI-based image processing efficiently.

## License

This project is licensed under the GNU AGPLv3 License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please submit issues or pull requests to help improve the project.
