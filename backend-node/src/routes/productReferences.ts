import { Router } from "express";
import multer from "multer";
import { prisma } from "../db.js";
import { uploadBuffer } from "../services/storageService.js";
import { createAsset } from "../services/productReferenceService.js";
import { AssetType } from "@prisma/client";
import { slugify } from "../utils/slug.js";
import axios from "axios";
import { config } from "../config.js";

export const productReferencesRouter = Router();
const upload = multer({ storage: multer.memoryStorage() });

productReferencesRouter.get("/", async (_req, res) => {
  const items = await prisma.productReference.findMany({
    include: { assets: true, geometryProfile: true },
    orderBy: { createdAt: "desc" },
    take: 100
  });
  res.json(items);
});

productReferencesRouter.post("/", async (req, res) => {
  const body = req.body;
  const slug = slugify(`${body.manufacturer}-${body.productName}`);

  const product = await prisma.productReference.create({
    data: {
      id: slug,
      slug,
      manufacturer: body.manufacturer,
      productName: body.productName,
      category: body.category,
      subcategory: body.subcategory,
      sourceUrl: body.sourceUrl,
      metadata: body.metadata || {}
    }
  });

  res.json(product);
});

productReferencesRouter.post("/:id/assets", upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "Missing file" });

  const product = await prisma.productReference.findUniqueOrThrow({
    where: { id: req.params.id }
  });

  const assetType = (req.body.assetType || "IMAGE") as AssetType;
  const folder =
    assetType === "IMAGE" ? "images" :
    assetType === "DWG" || assetType === "DXF" ? "cad" :
    assetType === "PDF" ? "specs" :
    "assets";

  const key = `raw/${product.manufacturer}/${product.slug}/${folder}/${req.file.originalname}`;
  const uploaded = await uploadBuffer({
    key,
    buffer: req.file.buffer,
    contentType: req.file.mimetype
  });

  const asset = await createAsset({
    productReferenceId: product.id,
    assetType,
    fileName: req.file.originalname,
    mimeType: uploaded.mimeType,
    spaceKey: uploaded.spaceKey,
    cdnUrl: uploaded.cdnUrl,
    fileHash: uploaded.fileHash
  });

  res.json(asset);
});

productReferencesRouter.post("/:id/process-dxf", async (req, res) => {
  const product = await prisma.productReference.findUniqueOrThrow({
    where: { id: req.params.id },
    include: { assets: true }
  });

  const dxf = product.assets.find((a) => a.assetType === "DXF");
  if (!dxf) return res.status(400).json({ error: "No DXF asset found" });

  const response = await axios.post(`${config.pythonWorkerUrl}/api/process-dxf`, {
    productId: product.id,
    manufacturer: product.manufacturer,
    productSlug: product.slug,
    dxfUrl: dxf.cdnUrl
  });

  res.json(response.data);
});
