import dotenv from "dotenv";
dotenv.config();

export const config = {
  port: Number(process.env.PORT || 4000),
  databaseUrl: process.env.DATABASE_URL!,
  spaces: {
    endpoint: process.env.SPACES_ENDPOINT!,
    region: process.env.SPACES_REGION || "sgp1",
    bucket: process.env.SPACES_BUCKET!,
    key: process.env.SPACES_KEY!,
    secret: process.env.SPACES_SECRET!,
    cdnBase: process.env.SPACES_CDN_BASE!
  },
  pythonWorkerUrl: process.env.PYTHON_WORKER_URL || "http://localhost:8001",
  qdrantUrl: process.env.QDRANT_URL || "http://localhost:6333"
};
