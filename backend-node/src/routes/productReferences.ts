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

/**
 * @openapi
 * /api/product-references:
 *   get:
 *     summary: List all product references
 *     tags: [Products]
 *     security: []
 *     responses:
 *       200:
 *         description: Array of products with assets and geometry profiles
 *   post:
 *     summary: Create a new product reference
 *     tags: [Products]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [manufacturer, productName]
 *             properties:
 *               manufacturer: { type: string }
 *               productName: { type: string }
 *               category: { type: string }
 *               sourceUrl: { type: string }
 *     responses:
 *       201:
 *         description: Created product
 */
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

/**
 * @openapi
 * /api/product-references/{id}/assets:
 *   post:
 *     summary: Upload an asset (DXF, image, PDF) to a product
 *     tags: [Products]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     requestBody:
 *       required: true
 *       content:
 *         multipart/form-data:
 *           schema:
 *             type: object
 *             properties:
 *               assetType:
 *                 type: string
 *                 enum: [IMAGE, DXF, DWG, PDF, SVG, STEP]
 *               file:
 *                 type: string
 *                 format: binary
 *     responses:
 *       201:
 *         description: Asset uploaded to Spaces
 */
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

/**
 * @openapi
 * /api/product-references/{id}/process-dxf:
 *   post:
 *     summary: Parse a product's DXF asset and index in Qdrant
 *     tags: [Products]
 *     description: Downloads the DXF from CDN, parses geometry, generates SVG preview, indexes in Qdrant vector search.
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200:
 *         description: Processing result with entity count and Qdrant status
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 status: { type: string }
 *                 entity_count: { type: integer }
 *                 qdrant: { type: object }
 */
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
