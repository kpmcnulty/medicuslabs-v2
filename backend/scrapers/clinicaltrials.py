from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate

class ClinicalTrialsScraper(BaseScraper):
    """Scraper for ClinicalTrials.gov using API v2"""
    
    BASE_URL = "https://clinicaltrials.gov/api/v2"
    
    def __init__(self, source_id: int = None):
        # Source ID 2 is ClinicalTrials.gov from our initial data
        super().__init__(source_id=source_id or 2, source_name="ClinicalTrials.gov", rate_limit=10.0)
    
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for clinical trials by disease term"""
        results = []
        page_token = None
        
        # Get max results from kwargs (passed by base class)
        max_results = kwargs.get('max_results', 100)
        
        # Check for incremental update parameters
        since_date = kwargs.get('since_date')
        
        while max_results is None or len(results) < max_results:
            # Build query parameters
            params = {
                "query.cond": disease_term,
                "pageSize": 100 if max_results is None else min(100, max_results - len(results)),
                "format": "json",
                "markupFormat": "markdown",  # Get markdown formatted text
                "sort": "LastUpdatePostDate"  # Sort by update date for incremental
            }
            
            if page_token:
                params["pageToken"] = page_token
            
            # Add date filter for incremental updates using the correct API syntax
            if since_date:
                # Use the correct API syntax for date filtering
                start_date = since_date.strftime("%Y-%m-%d")
                params["query.term"] = f"AREA[LastUpdatePostDate]RANGE[{start_date},MAX]"
            
            # Add any additional filters
            if kwargs.get("status"):
                params["filter.overallStatus"] = kwargs["status"]
            
            # Make request
            try:
                response = await self.make_request(f"{self.BASE_URL}/studies", params=params)
                
                # Extract studies
                studies = response.get("studies", [])
                results.extend(studies)
                
                # Check for next page
                page_token = response.get("nextPageToken")
                if not page_token or len(studies) == 0:
                    break
                    
            except Exception as e:
                logger.error(f"Error searching ClinicalTrials.gov for '{disease_term}': {e}")
                break
        
        logger.info(f"Found {len(results)} trials for '{disease_term}'")
        return results
    
    async def fetch_details(self, nct_id: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific trial"""
        try:
            response = await self.make_request(f"{self.BASE_URL}/studies/{nct_id}")
            return response
        except Exception as e:
            logger.error(f"Error fetching details for {nct_id}: {e}")
            raise
    
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform trial data"""
        protocol = raw_data.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        description = protocol.get("descriptionModule", {})
        status = protocol.get("statusModule", {})
        conditions = protocol.get("conditionsModule", {})
        interventions = protocol.get("armsInterventionsModule", {})
        outcomes = protocol.get("outcomesModule", {})
        
        # Extract NCT ID
        nct_id = identification.get("nctId", "")
        
        # Build title
        title = identification.get("briefTitle", "")
        if identification.get("officialTitle"):
            title = identification.get("officialTitle")
        
        # Build content
        content_parts = []
        
        # Brief summary
        if description.get("briefSummary"):
            content_parts.append(f"SUMMARY: {description['briefSummary']}")
        
        # Detailed description
        if description.get("detailedDescription"):
            content_parts.append(f"DESCRIPTION: {description['detailedDescription']}")
        
        # Eligibility criteria
        eligibility = protocol.get("eligibilityModule", {})
        if eligibility.get("eligibilityCriteria"):
            content_parts.append(f"ELIGIBILITY: {eligibility['eligibilityCriteria']}")
        
        # Conditions
        if conditions.get("conditions"):
            content_parts.append(f"CONDITIONS: {', '.join(conditions['conditions'])}")
        
        # Interventions
        if interventions.get("interventions"):
            intervention_names = [i.get("name", "") for i in interventions["interventions"]]
            content_parts.append(f"INTERVENTIONS: {', '.join(intervention_names)}")
        
        # Primary outcomes
        if outcomes.get("primaryOutcomes"):
            outcome_texts = []
            for o in outcomes["primaryOutcomes"]:
                measure = o.get("measure", "")
                time_frame = o.get("timeFrame", "")
                outcome_text = measure
                if time_frame:
                    outcome_text += f" [{time_frame}]"
                outcome_texts.append(outcome_text)
            content_parts.append(f"PRIMARY OUTCOMES: {'; '.join(outcome_texts)}")
        
        # Secondary outcomes
        if outcomes.get("secondaryOutcomes"):
            outcome_texts = []
            for o in outcomes["secondaryOutcomes"]:
                measure = o.get("measure", "")
                time_frame = o.get("timeFrame", "")
                outcome_text = measure
                if time_frame:
                    outcome_text += f" [{time_frame}]"
                outcome_texts.append(outcome_text)
            content_parts.append(f"SECONDARY OUTCOMES: {'; '.join(outcome_texts)}")
        
        content = "\n\n".join(content_parts)
        
        # Extract summary
        summary = description.get("briefSummary", "")[:500] if description.get("briefSummary") else ""
        
        # Extract phase as string (join if multiple phases)
        phases = status.get("phases", [])
        phase_str = ", ".join(phases) if phases else None
        
        # Extract enrollment from different possible locations
        enrollment = (
            status.get("enrollmentInfo", {}).get("count") or
            protocol.get("designModule", {}).get("enrollmentInfo", {}).get("count") or
            protocol.get("designModule", {}).get("enrollment", {}).get("count")
        )
        
        # Build metadata
        metadata = {
            "nct_id": nct_id,
            "status": status.get("overallStatus", ""),
            "phase": phase_str,
            "phases": phases,  # Keep original array too
            "study_type": protocol.get("designModule", {}).get("studyType", ""),
            "conditions": conditions.get("conditions", []),
            "keywords": conditions.get("keywords", []),
            "enrollment": enrollment,
            "enrollment_count": enrollment,  # Alternative field name
            "target_enrollment": enrollment,  # Another alternative
            "start_date": status.get("startDateStruct", {}).get("date"),
            "study_start_date": status.get("startDateStruct", {}).get("date"),  # Alternative field name
            "start_date_type": status.get("startDateStruct", {}).get("type"),
            "completion_date": status.get("completionDateStruct", {}).get("date"),
            "study_completion_date": status.get("completionDateStruct", {}).get("date"),  # Alternative field name
            "completion_date_type": status.get("completionDateStruct", {}).get("type"),
            "primary_completion_date": status.get("primaryCompletionDateStruct", {}).get("date"),
            "primary_completion_date_type": status.get("primaryCompletionDateStruct", {}).get("type"),
            "last_update": status.get("lastUpdatePostDateStruct", {}).get("date"),
            "eligibility": self._extract_eligibility(eligibility),
            "sponsors": self._extract_sponsors(protocol),
            "locations": self._extract_locations(protocol),
            "interventions": self._extract_interventions(interventions),
            "outcomes": self._extract_outcomes(outcomes)
        }
        
        # Build URL
        url = f"https://clinicaltrials.gov/study/{nct_id}"
        
        # Extract last update date
        last_update_str = status.get("lastUpdatePostDateStruct", {}).get("date")
        source_updated_at = None
        if last_update_str:
            try:
                source_updated_at = datetime.strptime(last_update_str, "%Y-%m-%d")
            except:
                pass
        
        return DocumentCreate(
            source_id=self.source_id,
            external_id=nct_id,
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
    
    def _extract_eligibility(self, eligibility_module: Dict[str, Any]) -> Dict[str, Any]:
        """Extract eligibility information"""
        return {
            "criteria": eligibility_module.get("eligibilityCriteria", ""),
            "gender": eligibility_module.get("sex", ""),
            "minimum_age": eligibility_module.get("minimumAge", ""),
            "maximum_age": eligibility_module.get("maximumAge", ""),
            "healthy_volunteers": eligibility_module.get("healthyVolunteers", "")
        }
    
    def _extract_sponsors(self, protocol: Dict[str, Any]) -> Dict[str, Any]:
        """Extract sponsor information"""
        sponsors_module = protocol.get("sponsorCollaboratorsModule", {})
        return {
            "lead_sponsor": sponsors_module.get("leadSponsor", {}).get("name"),
            "collaborators": [c.get("name") for c in sponsors_module.get("collaborators", [])]
        }
    
    def _extract_locations(self, protocol: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract location information"""
        locations = []
        contacts_module = protocol.get("contactsLocationsModule", {})
        
        for location in contacts_module.get("locations", []):
            locations.append({
                "facility": location.get("facility"),
                "city": location.get("city"),
                "state": location.get("state"),
                "country": location.get("country"),
                "status": location.get("status")
            })
        
        return locations
    
    def _extract_interventions(self, interventions_module: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract intervention details"""
        interventions = []
        
        for intervention in interventions_module.get("interventions", []):
            interventions.append({
                "type": intervention.get("type"),
                "name": intervention.get("name"),
                "description": intervention.get("description"),
                "arm_group_labels": intervention.get("armGroupLabels", [])
            })
        
        return interventions
    
    def _extract_outcomes(self, outcomes_module: Dict[str, Any]) -> Dict[str, Any]:
        """Extract outcome measures"""
        return {
            "primary": [
                {
                    "measure": o.get("measure"),
                    "description": o.get("description"),
                    "time_frame": o.get("timeFrame")
                }
                for o in outcomes_module.get("primaryOutcomes", [])
            ],
            "secondary": [
                {
                    "measure": o.get("measure"),
                    "description": o.get("description"),
                    "time_frame": o.get("timeFrame")
                }
                for o in outcomes_module.get("secondaryOutcomes", [])
            ]
        }