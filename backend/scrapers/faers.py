import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings

class FAERSScraper(BaseScraper):
    """FDA Adverse Event Reporting System (FAERS) scraper with cursor-based resume"""
    
    def __init__(self, source_id=None, source_name="FDA FAERS"):
        if source_id is None:
            source_id = 6
        super().__init__(source_id=source_id, source_name=source_name, rate_limit=1.0)
        self.BASE_URL = "https://api.fda.gov/drug/event.json"
        self.api_key = getattr(settings, 'fda_api_key', None)
    
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for adverse events with cursor-based resume"""
        max_results = kwargs.get('max_results')  # None = unlimited
        since_date = kwargs.get('since_date')
        
        # FDA API hard limit is 26000 skip + limit
        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_skip = cursor.get('skip', 0)
        exhausted = cursor.get('exhausted', False)
        newest_seen = cursor.get('newest_seen')
        
        if exhausted and not since_date:
            if newest_seen:
                logger.info(f"FAERS: Exhausted for '{disease_term}', incremental from {newest_seen}")
                since_date = datetime.strptime(newest_seen, "%Y%m%d") if isinstance(newest_seen, str) else newest_seen
                saved_skip = 0
            else:
                saved_skip = 0
        
        # Build search query
        search_parts = []
        if disease_term:
            search_parts.append(f'(patient.reaction.reactionmeddrapt:"{disease_term}" OR patient.drug.drugindication:"{disease_term}")')
        if since_date:
            date_str = since_date.strftime("%Y%m%d") if isinstance(since_date, datetime) else since_date
            search_parts.append(f'receivedate:[{date_str} TO *]')
        
        search_query = ' AND '.join(search_parts) if search_parts else ''
        
        page_size = 100  # FDA API max per request
        params = {
            "limit": page_size,
            "skip": saved_skip
        }
        if search_query:
            params["search"] = search_query
        if self.api_key:
            params["api_key"] = self.api_key
        params["sort"] = "receivedate:desc"
        
        all_results = []
        
        while max_results is None or len(all_results) < max_results:
            try:
                response = await self.make_request(self.BASE_URL, params=params)
                results = response.get("results", [])
                if not results:
                    await self.mark_exhausted(disease_term)
                    break
                
                all_results.extend(results)
                
                # Track newest date
                for r in results:
                    rd = r.get("receivedate", "")
                    if rd and (not newest_seen or rd > newest_seen):
                        newest_seen = rd
                
                meta = response.get("meta", {})
                total = meta.get("results", {}).get("total", 0)
                
                params["skip"] += page_size
                
                # Save cursor after each page
                await self.save_cursor(disease_term, skip=params["skip"], newest_seen=newest_seen)
                
                if params["skip"] >= total or params["skip"] >= 26000:
                    # FDA API caps at skip=26000
                    await self.mark_exhausted(disease_term)
                    break
                    
            except Exception as e:
                logger.error(f"Error searching FAERS for '{disease_term}': {e}")
                await self.save_cursor(disease_term, skip=params["skip"], newest_seen=newest_seen)
                break
        
        if max_results:
            all_results = all_results[:max_results]
        
        logger.info(f"Found {len(all_results)} adverse event reports for '{disease_term}'")
        return all_results
    
    async def fetch_details(self, report_id: str) -> Dict[str, Any]:
        params = {"search": f'safetyreportid:"{report_id}"', "limit": 1}
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            response = await self.make_request(self.BASE_URL, params=params)
            results = response.get("results", [])
            return results[0] if results else {}
        except Exception as e:
            logger.error(f"Error fetching FAERS report {report_id}: {e}")
            return {}
    
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        report_id = raw_data.get("safetyreportid", "")
        if not report_id:
            receipt_date = raw_data.get("receiptdate", "")
            report_id = f"FAERS_{receipt_date}_{hash(str(raw_data))}"
        
        patient = raw_data.get("patient", {})
        
        reactions = []
        reaction_outcomes = []
        for reaction in patient.get("reaction", []):
            reaction_term = reaction.get("reactionmeddrapt", "")
            if reaction_term:
                reactions.append(reaction_term)
            outcome = reaction.get("reactionoutcome", "")
            if outcome:
                reaction_outcomes.append(self._decode_outcome(outcome))
        
        drugs = []
        drug_details = []
        for drug in patient.get("drug", []):
            drug_name = drug.get("medicinalproduct", "") or drug.get("openfda", {}).get("generic_name", [""])[0]
            if drug_name:
                drugs.append(drug_name)
            drug_details.append({
                "name": drug_name,
                "dose": drug.get("drugdosagetext", ""),
                "route": drug.get("drugadministrationroute", ""),
                "indication": drug.get("drugindication", ""),
                "action": drug.get("actiondrug", ""),
                "start_date": drug.get("drugstartdate", ""),
                "end_date": drug.get("drugenddate", "")
            })
        
        demographics = {
            "age": patient.get("patientonsetage", ""),
            "age_unit": patient.get("patientonsetageunit", ""),
            "sex": self._decode_sex(patient.get("patientsex", "")),
            "weight": patient.get("patientweight", ""),
            "death": patient.get("patientdeath", {})
        }
        
        content_parts = []
        if reactions:
            content_parts.append(f"ADVERSE EVENTS: {', '.join(reactions)}")
        if drugs:
            content_parts.append(f"SUSPECT DRUGS: {', '.join(drugs)}")
        if reaction_outcomes:
            content_parts.append(f"OUTCOMES: {', '.join(set(reaction_outcomes))}")
        demo_text = []
        if demographics["age"]:
            demo_text.append(f"Age: {demographics['age']} {demographics['age_unit']}")
        if demographics["sex"]:
            demo_text.append(f"Sex: {demographics['sex']}")
        if demo_text:
            content_parts.append(f"PATIENT: {', '.join(demo_text)}")
        reporter = raw_data.get("primarysource", {})
        if reporter.get("reportercountry"):
            content_parts.append(f"COUNTRY: {reporter['reportercountry']}")
        
        content = "\n\n".join(content_parts)
        primary_reaction = reactions[0] if reactions else "Adverse Event"
        primary_drug = drugs[0] if drugs else "Unknown Drug"
        title = f"{primary_reaction} associated with {primary_drug}"
        summary = f"Report of {', '.join(reactions[:3])} in patient taking {', '.join(drugs[:3])}"
        if len(reactions) > 3:
            summary += f" and {len(reactions)-3} more reactions"
        
        receive_date = raw_data.get("receivedate", "")
        receipt_date = raw_data.get("receiptdate", "")
        
        metadata = {
            "safety_report_id": report_id,
            "case_version": raw_data.get("safetyreportversion", ""),
            "report_type": raw_data.get("serious", ""),
            "seriousness_criteria": self._extract_seriousness(raw_data),
            "receive_date": receive_date, "receipt_date": receipt_date,
            "qualification": reporter.get("qualification", ""),
            "patient_demographics": demographics,
            "reactions": reactions, "reaction_outcomes": reaction_outcomes,
            "drugs": drug_details, "drug_names": drugs,
            "reporter_country": reporter.get("reportercountry", ""),
            "reporter_qualification": reporter.get("qualification", ""),
            "manufacturer_name": raw_data.get("companynumb", ""),
            "fulfill_expedite": raw_data.get("fulfillexpeditecriteria", ""),
            "source": "FDA FAERS"
        }
        
        url = f"https://api.fda.gov/drug/event.json?search=safetyreportid:\"{report_id}\""
        source_updated_at = None
        try:
            if receive_date:
                source_updated_at = datetime.strptime(receive_date, "%Y%m%d")
        except:
            pass
        
        return DocumentCreate(
            source_id=self.source_id, external_id=report_id, url=url,
            title=title, content=content, summary=summary, metadata=metadata
        ), source_updated_at
    
    def _decode_outcome(self, outcome_code: str) -> str:
        outcomes = {"1": "Recovered", "2": "Recovering", "3": "Not recovered",
                    "4": "Recovered with sequelae", "5": "Fatal", "6": "Unknown"}
        return outcomes.get(outcome_code, outcome_code)
    
    def _decode_sex(self, sex_code: str) -> str:
        return {"0": "Unknown", "1": "Male", "2": "Female"}.get(sex_code, sex_code)
    
    def _extract_seriousness(self, raw_data: Dict[str, Any]) -> List[str]:
        criteria = []
        if raw_data.get("seriousnessdeath") == "1": criteria.append("Death")
        if raw_data.get("seriousnesslifethreatening") == "1": criteria.append("Life Threatening")
        if raw_data.get("seriousnesshospitalization") == "1": criteria.append("Hospitalization")
        if raw_data.get("seriousnessdisabling") == "1": criteria.append("Disabling")
        if raw_data.get("seriousnesscongenitalanomali") == "1": criteria.append("Congenital Anomaly")
        if raw_data.get("seriousnessother") == "1": criteria.append("Other Serious")
        return criteria
