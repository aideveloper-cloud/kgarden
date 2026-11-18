-- Multi-level BOM explosion (PostgreSQL, read-only).
--
-- Parameters:
--   $1  item_code of the item to build (uses its active, default, submitted BOM)
--   $2  quantity to build, in the item's stock UOM
--
-- Returns one row per BOM line at every level, in tree order:
--   level, item_tree (indented), parent_item, item_code, item_name,
--   required_qty (stock UOM, already scaled by every parent BOM's batch size),
--   stock_uom, is_leaf (true = purchased/raw, no BOM below it),
--   unit_cost (BOM line base rate per stock UOM), line_cost (leaf rows only)
--
-- The total material cost is SUM(line_cost). Sub-assembly rows carry no cost so it is not counted twice.
-- Suitable for the read-only reporting role on the replica; it touches only tabBOM, tabBOM Item and tabItem.

WITH RECURSIVE root AS (
	SELECT b.name, b.item, b.quantity
	FROM "tabBOM" b
	WHERE b.item = $1
		AND b.is_active = 1
		AND b.is_default = 1
		AND b.docstatus = 1
	ORDER BY b.modified DESC
	LIMIT 1
),
tree AS (
	SELECT
		1 AS level,
		r.item AS parent_item,
		bi.item_code,
		NULLIF(bi.bom_no, '') AS bom_no,
		bi.stock_qty / r.quantity * $2::numeric AS required_qty,
		bi.stock_uom,
		bi.base_rate / NULLIF(bi.conversion_factor, 0) AS unit_cost,
		ARRAY[r.item::text, bi.item_code::text] AS path,
		lpad(bi.idx::text, 4, '0') AS sort_key
	FROM root r
	JOIN "tabBOM Item" bi
		ON bi.parent = r.name AND bi.parenttype = 'BOM' AND bi.parentfield = 'items'

	UNION ALL

	SELECT
		t.level + 1,
		b.item,
		bi.item_code,
		NULLIF(bi.bom_no, ''),
		bi.stock_qty / b.quantity * t.required_qty,
		bi.stock_uom,
		bi.base_rate / NULLIF(bi.conversion_factor, 0),
		t.path || bi.item_code::text,
		t.sort_key || '.' || lpad(bi.idx::text, 4, '0')
	FROM tree t
	JOIN "tabBOM" b
		ON b.name = t.bom_no AND b.docstatus = 1
	JOIN "tabBOM Item" bi
		ON bi.parent = b.name AND bi.parenttype = 'BOM' AND bi.parentfield = 'items'
	WHERE NOT (bi.item_code = ANY (t.path)) -- guard against a cyclic BOM
)
SELECT
	t.level,
	repeat('  ', t.level - 1) || t.item_code AS item_tree,
	t.parent_item,
	t.item_code,
	i.item_name,
	round(t.required_qty, 6) AS required_qty,
	t.stock_uom,
	t.bom_no IS NULL AS is_leaf,
	round(t.unit_cost, 4) AS unit_cost,
	CASE WHEN t.bom_no IS NULL THEN round(t.required_qty * t.unit_cost, 2) END AS line_cost
FROM tree t
JOIN "tabItem" i ON i.name = t.item_code
ORDER BY t.sort_key;
