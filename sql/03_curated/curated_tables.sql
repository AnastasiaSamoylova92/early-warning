
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'curated')
BEGIN
	EXEC('CREATE SCHEMA curated')
END;

-- Erstellung Date Table
DROP TABLE IF EXISTS curated.dimDate;

CREATE TABLE curated.dimDate(
	DateKey INT PRIMARY KEY,
	[Date] DATE NOT NULL,
	[Year] INT NOT NULL,
	[Quarter] INT NOT NULL,
	QuarterName VARCHAR(2) NOT NULL,
	[Month] INT NOT NULL,
	MonthName VARCHAR(20) NOT NULL,
	MonthShortName VARCHAR(3) NOT NULL,
	YearMonth CHAR(7) NOT NULL,
	YearMonthKey INT NOT NULL,
	MonthStartDate DATE NOT NULL,
	MonthEndDate DATE NOT NULL,
	[Day] INT NOT NULL,
	DayOfWeek INT NOT NULL,
	DayName VARCHAR(20) NOT NULL,
	WeekOfYear INT NOT NULL,
	ISOWeek INT NOT NULL,
	IsWeekend BIT NOT NULL);

-- Zeitraum definieren
DECLARE @StartDate DATE = '2020-01-01';
DECLARE @EndDate DATE = '2030-12-31';

-- Date table befüllen
WITH DateSeries AS (
    SELECT @StartDate AS [Date]

    UNION ALL

    SELECT DATEADD(DAY, 1, [Date])
    FROM DateSeries
    WHERE [Date] < @EndDate
)
INSERT INTO curated.dimDate (
    DateKey,
    [Date],
    [Year],
    [Quarter],
    QuarterName,
    [Month],
    MonthName,
    MonthShortName,
    YearMonth,
    YearMonthKey,
    MonthStartDate,
    MonthEndDate,
    [Day],
    DayOfWeek,
    DayName,
    WeekOfYear,
    ISOWeek,
    IsWeekend
)
SELECT
    CAST(FORMAT([Date], 'yyyyMMdd') AS INT) AS DateKey,
    [Date],
    YEAR([Date]) AS [Year],
    DATEPART(QUARTER, [Date]) AS [Quarter],
    CONCAT('Q', DATEPART(QUARTER, [Date])) AS QuarterName,
    MONTH([Date]) AS [Month],
    DATENAME(MONTH, [Date]) AS MonthName,
    LEFT(DATENAME(MONTH, [Date]), 3) AS MonthShortName,
    FORMAT([Date], 'yyyy-MM') AS YearMonth,
    CAST(FORMAT([Date], 'yyyyMM') AS INT) AS YearMonthKey,
    DATEFROMPARTS(YEAR([Date]), MONTH([Date]), 1) AS MonthStartDate,
    EOMONTH([Date]) AS MonthEndDate,
    DAY([Date]) AS [Day],
    DATEPART(WEEKDAY, [Date]) AS DayOfWeek,
    DATENAME(WEEKDAY, [Date]) AS DayName,
    DATEPART(WEEK, [Date]) AS WeekOfYear,
    DATEPART(ISO_WEEK, [Date]) AS ISOWeek,
    CASE 
        WHEN DATENAME(WEEKDAY, [Date]) IN ('Saturday', 'Sunday') THEN 1 
        ELSE 0 
    END AS IsWeekend
FROM DateSeries
OPTION (MAXRECURSION 0);

SELECT TOP 10 * 
FROM curated.dimDate 
ORDER BY [Date];