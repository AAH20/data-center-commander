-- Fail closed when a takeoff line pins a mismatched, stale, or unapproved rate.
BEGIN;
CREATE OR REPLACE FUNCTION dcc.validate_estimate_price_link() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record;
BEGIN
 IF NEW.pricing_status='sourced' AND NEW.price_observation_id IS NULL THEN
  RAISE EXCEPTION 'sourced estimate line requires a pinned price observation';
 END IF;
 IF NEW.price_observation_id IS NULL THEN RETURN NEW; END IF;
 SELECT po.quantity_unit,po.normalized_unit_price,po.geography,po.valid_from,po.valid_to,po.quality_status,
        cb.currency AS book_currency,cb.status AS book_status,cb.valid_from AS book_from,cb.valid_to AS book_to,
        ep.currency AS estimate_currency,ep.geography AS estimate_geography,ep.price_as_of
 INTO p FROM dcc.price_observations po JOIN dcc.cost_books cb ON cb.tenant_id=po.tenant_id AND cb.id=po.cost_book_id
 JOIN dcc.estimate_projects ep ON ep.tenant_id=NEW.tenant_id AND ep.id=NEW.estimate_id
 WHERE po.tenant_id=NEW.tenant_id AND po.id=NEW.price_observation_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'price observation is not in the estimate tenant'; END IF;
 IF p.quality_status<>'approved' OR p.book_status<>'approved' THEN RAISE EXCEPTION 'estimate price and cost book must be approved'; END IF;
 IF p.quantity_unit<>NEW.quantity_unit OR p.book_currency<>NEW.currency OR p.estimate_currency<>NEW.currency
    OR upper(p.geography)<>upper(p.estimate_geography) THEN RAISE EXCEPTION 'estimate price unit, currency, or geography mismatch'; END IF;
 IF p.valid_from>p.price_as_of OR (p.valid_to IS NOT NULL AND p.valid_to<=p.price_as_of)
    OR p.book_from>p.price_as_of OR (p.book_to IS NOT NULL AND p.book_to<=p.price_as_of)
    OR NEW.base_unit_cost<>p.normalized_unit_price THEN RAISE EXCEPTION 'pinned price is out of date or not normalized to the estimate currency'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER estimate_price_link_check BEFORE INSERT OR UPDATE OF tenant_id,estimate_id,quantity_unit,currency,base_unit_cost,price_observation_id,pricing_status
 ON dcc.estimate_line_items FOR EACH ROW EXECUTE FUNCTION dcc.validate_estimate_price_link();
COMMIT;
