/**
 * E2E Integration Test — validates the full pipeline:
 * Product reference → DXF upload → Process → Qdrant index → Progress events
 */
const BASE = process.env.API_BASE || "http://localhost:4000";

async function test() {
  const pass = [];
  const fail = [];

  // 1. Create product
  try {
    const r = await fetch(`${BASE}/api/product-references`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        manufacturer: "e2e",
        productName: "E2E Test Table",
        category: "table",
      }),
    });
    const p = await r.json();
    console.log(`1. PASS: Product ${p.id}`);
    pass.push("create-product");

    // 2. Upload DXF
    try {
      const dxf = [
        "  0\nSECTION\n  2\nHEADER\n  9\n$ACADVER\n  1\nAC1021\n  0\nENDSEC",
        "  0\nSECTION\n  2\nENTITIES",
        "  0\nLINE\n  8\n0\n 10\n0.0\n 20\n0.0\n 30\n0.0\n 11\n100.0\n 21\n50.0\n 30\n0.0",
        "  0\nCIRCLE\n  8\n0\n 10\n50.0\n 20\n25.0\n 30\n0.0\n 40\n20.0",
        "  0\nENDSEC\n  0\nEOF",
      ].join("\n");
      const fd = new FormData();
      fd.append("assetType", "DXF");
      fd.append("file", new Blob([dxf], { type: "application/dxf" }), "e2e-table.dxf");
      const ar = await fetch(`${BASE}/api/product-references/${p.id}/assets`, {
        method: "POST",
        body: fd,
      });
      const a = await ar.json();
      console.log(`2. PASS: DXF uploaded to ${a.spaceKey || "local"}`);
      pass.push("upload-dxf");

      // 3. Process DXF
      try {
        const pr = await fetch(
          `${BASE}/api/product-references/${p.id}/process-dxf`,
          { method: "POST", headers: { "Content-Type": "application/json" } }
        );
        const proc = await pr.json();
        console.log(
          `3. PASS: Processed — ${proc.entity_count} entities, Qdrant: ${proc.qdrant?.status}`
        );
        pass.push("process-dxf");

        // 4. Check Qdrant
        try {
          await new Promise((r) => setTimeout(r, 3000));
          const qr = await fetch("http://qdrant:6333/collections/cad_geometry");
          const q = await qr.json();
          console.log(`4. PASS: Qdrant has ${q.result.points_count} points`);
          pass.push("qdrant-index");
        } catch (e) {
          fail.push(`qdrant: ${e.message}`);
        }

        // 5. Progress buffer
        try {
          const ppr = await fetch("http://python-worker:8001/api/progress");
          const pp = await ppr.json();
          console.log(`5. PASS: Progress buffer has ${pp.count} events`);
          pass.push("progress");
        } catch (e) {
          fail.push(`progress: ${e.message}`);
        }
      } catch (e) {
        fail.push(`process-dxf: ${e.message}`);
      }
    } catch (e) {
      fail.push(`upload-dxf: ${e.message}`);
    }
  } catch (e) {
    fail.push(`create-product: ${e.message}`);
  }

  console.log("\n======= E2E TEST SUMMARY =======");
  console.log(`PASSED: ${pass.length}  FAILED: ${fail.length}`);
  fail.forEach((f) => console.log(`  FAIL: ${f}`));
  process.exit(fail.length > 0 ? 1 : 0);
}

test().catch((e) => {
  console.error(`FATAL: ${e.message}`);
  process.exit(1);
});
