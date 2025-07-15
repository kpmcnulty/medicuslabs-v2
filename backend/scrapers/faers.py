import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings

class FAERSScraper(BaseScraper):
    """FDA Adverse Event Reporting System (FAERS) scraper"""
    
    def __init__(self, source_id=None, source_name="FDA FAERS"):
        # If source_id not provided, we'll get it from the database
        if source_id is None:
            # This will be set by the task when it runs
            source_id = 6  # Placeholder - will be overridden
        super().__init__(source_id=source_id, source_name=source_name, rate_limit=1.0)  # Conservative rate limit
        self.BASE_URL = "https://api.fda.gov/drug/event.json"
        self.api_key = getattr(settings, 'fda_api_key', None)
    
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for adverse events related to a disease/drug"""
        # Get max results from kwargs
        max_results = kwargs.get('max_results', 100)
        if max_results is None:
            max_results = 1000  # FDA API max is 1000 per query
        
        # Check for incremental update
        since_date = kwargs.get('since_date')
        
        # Build search query - search in patient.reaction.reactionmeddrapt field
        # This field contains the adverse event/reaction descriptions
        search_parts = []
        
        # Search for the disease term in reactions
        if disease_term:
            # Search in reaction field and drug indications
            search_parts.append(f'(patient.reaction.reactionmeddrapt:"{disease_term}" OR patient.drug.drugindication:"{disease_term}")')
        
        # Add date filter for incremental updates
        if since_date:
            date_str = since_date.strftime("%Y%m%d")
            search_parts.append(f'receivedate:[{date_str} TO *]')
        
        # Combine search parts
        search_query = ' AND '.join(search_parts) if search_parts else ''
        
        params = {
            "limit": min(max_results, 100),  # FDA API allows max 100 per request
            "skip": 0
        }
        
        if search_query:
            params["search"] = search_query
        
        # Add API key if available
        if self.api_key:
            params["api_key"] = self.api_key
        
        # Sort by receive date (most recent first)
        params["sort"] = "receivedate:desc"
        
        all_results = []
        
        # Handle pagination
        while max_results is None or len(all_results) < max_results:
            try:
                response = await self.make_request(self.BASE_URL, params=params)
                
                # Extract results
                results = response.get("results", [])
                if not results:
                    break
                
                all_results.extend(results)
                
                # Check if there are more results
                meta = response.get("meta", {})
                total = meta.get("results", {}).get("total", 0)
                
                if params["skip"] + params["limit"] >= total:
                    break
                
                # Move to next page
                params["skip"] += params["limit"]
                
                # Check if we've collected enough
                if max_results and len(all_results) >= max_results:
                    break
                    
            except Exception as e:
                logger.error(f"Error searching FAERS for '{disease_term}': {e}")
                break
        
        # Trim to max_results
        if max_results:
            all_results = all_results[:max_results]
        
        logger.info(f"Found {len(all_results)} adverse event reports for '{disease_term}'")
        return all_results
    
    async def fetch_details(self, report_id: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific report"""
        # FAERS API returns full details in search results, so we don't need separate fetch
        params = {
            "search": f'safetyreportid:"{report_id}"',
            "limit": 1
        }
        
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
        """Extract and transform FAERS report data"""
        # Extract report ID
        report_id = raw_data.get("safetyreportid", "")
        if not report_id:
            # Generate ID from other fields if missing
            receipt_date = raw_data.get("receiptdate", "")
            report_id = f"FAERS_{receipt_date}_{hash(str(raw_data))}"
        
        # Extract patient information
        patient = raw_data.get("patient", {})
        
        # Extract reactions (adverse events)
        reactions = []
        reaction_outcomes = []
        for reaction in patient.get("reaction", []):
            reaction_term = reaction.get("reactionmeddrapt", "")
            if reaction_term:
                reactions.append(reaction_term)
            outcome = reaction.get("reactionoutcome", "")
            if outcome:
                reaction_outcomes.append(self._decode_outcome(outcome))
        
        # Extract drug information
        drugs = []
        drug_details = []
        for drug in patient.get("drug", []):
            drug_name = drug.get("medicinalproduct", "") or drug.get("openfda", {}).get("generic_name", [""])[0]
            if drug_name:
                drugs.append(drug_name)
                
            drug_info = {
                "name": drug_name,
                "dose": drug.get("drugdosagetext", ""),
                "route": drug.get("drugadministrationroute", ""),
                "indication": drug.get("drugindication", ""),
                "action": drug.get("actiondrug", ""),
                "start_date": drug.get("drugstartdate", ""),
                "end_date": drug.get("drugenddate", "")
            }
            drug_details.append(drug_info)
        
        # Extract patient demographics
        demographics = {
            "age": patient.get("patientonsetage", ""),
            "age_unit": patient.get("patientonsetageunit", ""),
            "sex": self._decode_sex(patient.get("patientsex", "")),
            "weight": patient.get("patientweight", ""),
            "death": patient.get("patientdeath", {})
        }
        
        # Build content
        content_parts = []
        
        if reactions:
            content_parts.append(f"ADVERSE EVENTS: {', '.join(reactions)}")
        
        if drugs:
            content_parts.append(f"SUSPECT DRUGS: {', '.join(drugs)}")
        
        if reaction_outcomes:
            content_parts.append(f"OUTCOMES: {', '.join(set(reaction_outcomes))}")
        
        # Add demographics if available
        demo_text = []
        if demographics["age"]:
            demo_text.append(f"Age: {demographics['age']} {demographics['age_unit']}")
        if demographics["sex"]:
            demo_text.append(f"Sex: {demographics['sex']}")
        if demo_text:
            content_parts.append(f"PATIENT: {', '.join(demo_text)}")
        
        # Add report details
        reporter = raw_data.get("primarysource", {})
        if reporter.get("reportercountry"):
            content_parts.append(f"COUNTRY: {reporter['reportercountry']}")
        
        content = "\n\n".join(content_parts)
        
        # Build title
        primary_reaction = reactions[0] if reactions else "Adverse Event"
        primary_drug = drugs[0] if drugs else "Unknown Drug"
        title = f"{primary_reaction} associated with {primary_drug}"
        
        # Summary
        summary = f"Report of {', '.join(reactions[:3])} in patient taking {', '.join(drugs[:3])}"
        if len(reactions) > 3:
            summary += f" and {len(reactions)-3} more reactions"
        
        # Extract dates
        receive_date = raw_data.get("receivedate", "")
        receipt_date = raw_data.get("receiptdate", "")
        
        # Build metadata
        metadata = {
            # Report identifiers
            "safety_report_id": report_id,
            "case_version": raw_data.get("safetyreportversion", ""),
            "report_type": raw_data.get("serious", ""),
            "seriousness_criteria": self._extract_seriousness(raw_data),
            
            # Dates
            "receive_date": receive_date,
            "receipt_date": receipt_date,
            "qualification": reporter.get("qualification", ""),
            
            # Patient info
            "patient_demographics": demographics,
            
            # Reactions
            "reactions": reactions,
            "reaction_outcomes": reaction_outcomes,
            
            # Drugs
            "drugs": drug_details,
            "drug_names": drugs,
            
            # Reporter info
            "reporter_country": reporter.get("reportercountry", ""),
            "reporter_qualification": reporter.get("qualification", ""),
            
            # Manufacturer info
            "manufacturer_name": raw_data.get("companynumb", ""),
            "fulfill_expedite": raw_data.get("fulfillexpeditecriteria", ""),
            
            # Source type
            "source": "FDA FAERS"
        }
        
        # Build URL (link to openFDA)
        url = f"https://api.fda.gov/drug/event.json?search=safetyreportid:\"{report_id}\""
        
        # Extract source update date
        source_updated_at = None
        try:
            if receive_date:
                source_updated_at = datetime.strptime(receive_date, "%Y%m%d")
        except:
            pass
        
        return DocumentCreate(
            source_id=self.source_id,
            external_id=report_id,
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata,
            scraped_at=datetime.now()
        ), source_updated_at
    
    def _decode_outcome(self, outcome_code: str) -> str:
        """Decode reaction outcome codes"""
        outcomes = {
            "1": "Recovered",
            "2": "Recovering",
            "3": "Not recovered",
            "4": "Recovered with sequelae",
            "5": "Fatal",
            "6": "Unknown"
        }
        return outcomes.get(outcome_code, outcome_code)
    
    def _decode_sex(self, sex_code: str) -> str:
        """Decode patient sex codes"""
        sex_map = {
            "0": "Unknown",
            "1": "Male", 
            "2": "Female"
        }
        return sex_map.get(sex_code, sex_code)
    
    def _extract_seriousness(self, raw_data: Dict[str, Any]) -> List[str]:
        """Extract seriousness criteria"""
        criteria = []
        
        if raw_data.get("seriousnessdeath") == "1":
            criteria.append("Death")
        if raw_data.get("seriousnesslifethreatening") == "1":
            criteria.append("Life Threatening")
        if raw_data.get("seriousnesshospitalization") == "1":
            criteria.append("Hospitalization")
        if raw_data.get("seriousnessdisabling") == "1":
            criteria.append("Disabling")
        if raw_data.get("seriousnesscongenitalanomali") == "1":
            criteria.append("Congenital Anomaly")
        if raw_data.get("seriousnessother") == "1":
            criteria.append("Other Serious")
            
        return criteria