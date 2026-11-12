SELECT
    x.EventName as EventName,
    ba.TransEmployee as TransEmployee,
    x.ParsedDate AS OfferDate,
	ba.AdjustmentDate as AdjustmentDate,
    p.Universalplayerid,
    ba.AdjustmentAmount,
    ba.AdjustmentAction
FROM ENGAGEDB.dbo.UC_PL_BucketAdjustment ba
LEFT JOIN ENGAGEDB.dbo.uc_pl_player p
    ON p.PlayerID = ba.PlayerID
CROSS APPLY (
    SELECT
        pos = PATINDEX('%[_][12][0-9][0-9][0-9]%', ba.TransEmployee)
) m
CROSS APPLY (
    SELECT
        EventName = CASE WHEN m.pos > 0 THEN LEFT(ba.TransEmployee, m.pos - 1) ELSE ba.TransEmployee END,
        RawDatePart = CASE WHEN m.pos > 0 THEN SUBSTRING(ba.TransEmployee, m.pos + 1, LEN(ba.TransEmployee)) ELSE NULL END
) x2
CROSS APPLY (
    SELECT
        EventName = x2.EventName,
        DigitsOnly = REPLACE(REPLACE(x2.RawDatePart, '-', ''), '_', '')
) x1
CROSS APPLY (
    SELECT
        EventName = x1.EventName,
        ParsedDate = TRY_CONVERT(date, LEFT(x1.DigitsOnly, 8), 112)
) x
WHERE ba.CreatedBy = 'HALoWebService'
  AND ba.AdjustmentDate >= '{{ADJUSTMENT_START}}'
  AND ba.AdjustmentDate < '{{ADJUSTMENT_END}}'
