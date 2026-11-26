# Global Financial Data and Market Research Sources


**Search terms:** market data, stock prices, financial data, exchange rates, economic indicators, global markets, official data sources, finance APIs.

This is a source directory for building an offline reference collection. These links are not bundled datasets and OUTPOST does not fetch them automatically. Check terms, redistribution rights, API limits, geographic coverage and update frequency before importing anything.

## Market structure, investor education and regulation
- **IOSCO** — https://www.iosco.org/ — international securities-regulator cooperation, principles and reports.
- **BIS** — https://www.bis.org/ — central banking, financial stability, banking and payment-system research.
- **IMF** — https://www.imf.org/en/Data — international macroeconomic and financial datasets, country reports and methodology.
- **World Bank Data** — https://data.worldbank.org/ — development indicators, country series and metadata.
- **OECD Data Explorer** — https://data-explorer.oecd.org/ — comparable economic and social indicators for covered economies.
- **UNCTAD Data Hub** — https://unctadstat.unctad.org/ — trade, investment, shipping and development statistics.
- **FRED** — https://fred.stlouisfed.org/ — broad economic time series; US-focused, with international series too.
- **SEC Investor.gov** — https://www.investor.gov/ — US investor education and fraud-awareness material; US jurisdiction only.
- **FINRA Investor Education** — https://www.finra.org/investors — US securities-market education and broker-check resources; US jurisdiction only.
- **Investor.gov EDGAR / SEC filings** — https://www.sec.gov/edgar/search/ — US issuer filings; not a worldwide company registry.

## Exchange and company primary sources
For any company or instrument, start with the relevant exchange, issuer investor-relations page, official regulator, prospectus and audited reports. Global exchanges include (examples, not a complete list):
- NYSE / Nasdaq (United States)
- London Stock Exchange (United Kingdom)
- Euronext (multiple European markets)
- Deutsche Börse / Frankfurt (Germany)
- SIX Swiss Exchange (Switzerland)
- Toronto Stock Exchange (Canada)
- B3 (Brazil)
- Japan Exchange Group / Tokyo Stock Exchange (Japan)
- Korea Exchange (South Korea)
- Shanghai Stock Exchange and Shenzhen Stock Exchange (China)
- Hong Kong Exchanges and Clearing (Hong Kong)
- National Stock Exchange of India and BSE (India)
- Australian Securities Exchange (Australia)
- Singapore Exchange (Singapore)
- Johannesburg Stock Exchange (South Africa)

Exchange rules, market hours, settlement, investor protections and product availability differ. Confirm the exact venue and jurisdiction.

## Suggested offline datasets
1. **Economic indicators:** GDP, inflation, employment, policy rates, trade, public debt and population. Preserve series ID, units, seasonal adjustment, frequency, geography, observation date and revision date.
2. **Company reference records:** issuer name, legal domicile, exchange, ticker, ISIN or other stable identifier, sector, reporting currency and official filings URL.
3. **Historical market prices:** date/time, timezone, venue, currency, instrument identifier, OHLCV fields, corporate-action adjustment method and provider licence.
4. **Fund factsheets:** benchmark, holdings date, domicile, expense ratio, risk classification, distribution policy and source date.
5. **Financial literacy:** market mechanics, accounting, valuation, portfolio risk, investor protection and fraud prevention.

## Data integrity rules
- A downloaded price file is a historical snapshot, not a live quote.
- Record provider, URL, retrieval timestamp, coverage period, timezone, units, currency, licence and any transformations.
- Never merge different tickers solely because their names look similar. Verify exchange and security identifier.
- Adjusted and unadjusted prices answer different questions; retain the method.
- Economic series can be revised. Preserve vintage/release date if available.
- Do not scrape or redistribute data where the provider's terms prohibit it.
- Label missing coverage and stale records. Never fill gaps with invented values.
- Keep primary source documents distinct from commentary and educational summaries.

## Safety and jurisdiction
This guide is educational, not financial, tax or legal advice. Securities rules, tax treatment, deposit protection, broker licensing and investor compensation vary by jurisdiction. Check the official regulator and exchange in the relevant country before acting. Be wary of guaranteed returns, unsolicited investment offers, impersonation and pressure to transfer funds.
