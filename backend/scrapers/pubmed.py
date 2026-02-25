import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings

class PubMedScraper(BaseScraper):
    """Enhanced PubMed scraper with cursor-based resume and PMC full-text enrichment"""
    
    def __init__(self, source_id: int = None):
        rate_limit = 10.0 if settings.pubmed_api_key else 3.0
        super().__init__(source_id=source_id or 1, source_name="PubMed", rate_limit=rate_limit)
        self.api_key = settings.pubmed_api_key
        self.BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for articles by disease term with cursor-based resume"""
        max_results = kwargs.get('max_results')  # None = unlimited
        since_date = kwargs.get('since_date')

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_offset = cursor.get('offset', 0)
        exhausted = cursor.get('exhausted', False)
        newest_seen = cursor.get('newest_seen')

        if exhausted and not since_date:
            # Incremental mode: only get new articles since last run
            if newest_seen:
                logger.info(f"PubMed: Exhausted for '{disease_term}', incremental from {newest_seen}")
                since_date = datetime.strptime(newest_seen, "%Y/%m/%d") if isinstance(newest_seen, str) else newest_seen
                saved_offset = 0
            else:
                logger.info(f"PubMed: Exhausted for '{disease_term}' but no newest_seen, full re-scan")
                saved_offset = 0

        # Search for PMIDs
        pmids = await self._search_pmids(disease_term, max_results, since_date=since_date, start_offset=saved_offset)
        
        if not pmids:
            if not exhausted:
                await self.mark_exhausted(disease_term)
            logger.info(f"No articles found for '{disease_term}'")
            return []
        
        # Fetch FULL details in batches
        results = []
        batch_size = 20
        
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            try:
                batch_results = await self._fetch_enhanced_batch(batch_pmids)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"PubMed batch error at offset {saved_offset + i}: {e}")
                # Save cursor on error
                await self.save_cursor(disease_term, offset=saved_offset + i)
                break

            # Save cursor after each batch
            await self.save_cursor(disease_term, offset=saved_offset + i + batch_size)

        # Track newest publication date for incremental
        for r in results:
            pub_dates = r.get('publication_dates', {})
            for key in pub_dates:
                if pub_dates[key]:
                    if not newest_seen or pub_dates[key] > newest_seen:
                        newest_seen = pub_dates[key]

        if newest_seen:
            await self.save_cursor(disease_term, newest_seen=newest_seen)

        # If we got fewer PMIDs than requested, we've exhausted
        if max_results is None or len(pmids) < (max_results if max_results else float('inf')):
            await self.mark_exhausted(disease_term)
        
        logger.info(f"Found {len(results)} articles with ENHANCED data for '{disease_term}'")
        
        # Enrich with PMC full text
        results = await self._enrich_with_pmc_fulltext(results)
        
        return results
    
    async def _search_pmids(self, disease_term: str, max_results: int, since_date: datetime = None,
                            start_offset: int = 0, **kwargs) -> List[str]:
        """Search for PMIDs using esearch with resume support"""
        search_term = f"{disease_term}[Title/Abstract]"
        
        if since_date:
            date_str = since_date.strftime("%Y/%m/%d") if isinstance(since_date, datetime) else since_date
            search_term += f" AND {date_str}[Date - Create]:3000[Date - Create]"
        
        page_size = 10000  # PubMed allows up to 100000
        params = {
            "db": "pubmed",
            "term": search_term,
            "retmax": page_size,
            "retmode": "json",
            "sort": "date"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        all_pmids = []
        retstart = start_offset
        
        while max_results is None or len(all_pmids) < max_results:
            params["retstart"] = retstart
            
            try:
                response = await self.make_request(f"{self.BASE_URL}/esearch.fcgi", params=params)
                result = response.get("esearchresult", {})
                pmids = result.get("idlist", [])
                
                if not pmids:
                    break
                
                all_pmids.extend(pmids)
                
                count = int(result.get("count", 0))
                if retstart + page_size >= count:
                    break
                
                retstart += page_size
                
            except Exception as e:
                logger.error(f"Error searching PubMed for '{disease_term}': {e}")
                break
        
        if max_results:
            return all_pmids[:max_results]
        return all_pmids
    
    async def _fetch_enhanced_batch(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """Fetch COMPLETE details for a batch of PMIDs"""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "full"
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(f"{self.BASE_URL}/efetch.fcgi", params=params)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            articles = []
            
            for article in root.findall(".//PubmedArticle"):
                article_data = self._parse_complete_article(article)
                if article_data:
                    articles.append(article_data)
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching enhanced batch of PMIDs: {e}")
            return []
    
    def _parse_complete_article(self, article_element: ET.Element) -> Optional[Dict[str, Any]]:
        """Parse article XML element and extract EVERY available field"""
        try:
            medline = article_element.find(".//MedlineCitation")
            article = medline.find(".//Article")
            pubmed_data = article_element.find(".//PubmedData")
            
            pmid = medline.find(".//PMID").text
            title = article.find(".//ArticleTitle").text or ""
            
            # Abstract with labels
            abstract_elem = article.find(".//Abstract")
            abstract = ""
            abstract_parts = []
            if abstract_elem is not None:
                for abstract_text in abstract_elem.findall(".//AbstractText"):
                    label = abstract_text.get("Label", "")
                    text = abstract_text.text or ""
                    if label:
                        abstract_parts.append({"label": label, "text": text})
                        abstract += f"{label}: {text} "
                    else:
                        abstract_parts.append({"label": None, "text": text})
                        abstract += f"{text} "
                abstract = abstract.strip()
            
            # Authors with affiliations
            detailed_authors = []
            authors_simple = []
            author_list = article.find(".//AuthorList")
            if author_list is not None:
                for i, author in enumerate(author_list.findall(".//Author")):
                    author_info = {"position": i + 1}
                    last_name = author.find(".//LastName")
                    fore_name = author.find(".//ForeName")
                    if last_name is not None:
                        full_name = last_name.text
                        if fore_name is not None:
                            full_name = f"{fore_name.text} {last_name.text}"
                        author_info["name"] = full_name
                        authors_simple.append(full_name)
                    affiliations = []
                    for aff in author.findall(".//AffiliationInfo/Affiliation"):
                        if aff.text:
                            affiliations.append(aff.text)
                    author_info["affiliations"] = affiliations
                    for identifier in author.findall(".//Identifier"):
                        source = identifier.get("Source", "").upper()
                        if source == "ORCID":
                            author_info["orcid"] = identifier.text
                    detailed_authors.append(author_info)
            
            # Journal information
            journal = article.find(".//Journal")
            journal_title = ""
            issn = ""
            if journal is not None:
                title_elem = journal.find(".//Title")
                journal_title = title_elem.text if title_elem is not None else ""
                issn_elem = journal.find(".//ISSN")
                issn = issn_elem.text if issn_elem is not None else ""
            
            pub_dates = self._extract_publication_dates(journal, pubmed_data)
            identifiers = self._extract_article_identifiers(article)
            mesh_data = self._extract_mesh_terms(medline)
            
            keywords = []
            keyword_list = medline.find(".//KeywordList")
            if keyword_list is not None:
                for keyword in keyword_list.findall(".//Keyword"):
                    if keyword.text:
                        keywords.append(keyword.text)
            
            article_types = []
            type_list = article.find(".//PublicationTypeList")
            if type_list is not None:
                for pub_type in type_list.findall(".//PublicationType"):
                    if pub_type.text:
                        article_types.append(pub_type.text)
            
            grants = self._extract_grants(medline)
            chemicals = self._extract_chemicals(medline)
            pub_history = self._extract_publication_history(pubmed_data)
            references = self._extract_references(pubmed_data)
            comments = self._extract_comments_corrections(pubmed_data)
            
            suppl_mesh = []
            for suppl in medline.findall(".//SupplMeshName"):
                if suppl.text:
                    suppl_mesh.append(suppl.text)
            
            language_elem = article.find(".//Language")
            language = language_elem.text if language_elem is not None else "en"
            
            return {
                "pmid": pmid, "title": title, "abstract": abstract,
                "abstract_structured": abstract_parts, "language": language,
                "authors": authors_simple, "detailed_authors": detailed_authors,
                "journal": journal_title, "issn": issn,
                "publication_dates": pub_dates, "identifiers": identifiers,
                "mesh_terms": mesh_data["mesh_terms"],
                "mesh_major": mesh_data["mesh_major"],
                "mesh_minor": mesh_data["mesh_minor"],
                "suppl_mesh_terms": suppl_mesh, "keywords": keywords,
                "article_types": article_types, "grants": grants,
                "chemicals": chemicals, "publication_history": pub_history,
                "references_cited": references[:10],
                "comments_corrections": comments
            }
            
        except Exception as e:
            logger.error(f"Error parsing enhanced article: {e}")
            return None
    
    def _extract_publication_dates(self, journal, pubmed_data) -> Dict[str, Any]:
        """Extract all publication dates"""
        dates = {}
        if journal is not None:
            pub_date = journal.find(".//PubDate")
            if pub_date is not None:
                year_elem = pub_date.find(".//Year")
                month_elem = pub_date.find(".//Month")
                day_elem = pub_date.find(".//Day")
                if year_elem is not None:
                    year = year_elem.text
                    month = month_elem.text if month_elem is not None else "01"
                    day = day_elem.text if day_elem is not None else "01"
                    if month and not month.isdigit():
                        month_map = {
                            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                        }
                        month = month_map.get(month[:3], '01')
                    else:
                        month = month.zfill(2) if month else "01"
                    day = day.zfill(2) if day else "01"
                    dates["published"] = f"{year}-{month}-{day}"
        if pubmed_data is not None:
            for date_elem in pubmed_data.findall(".//ArticleDate"):
                date_type = date_elem.get("DateType", "Electronic")
                year_elem = date_elem.find(".//Year")
                month_elem = date_elem.find(".//Month")
                day_elem = date_elem.find(".//Day")
                if year_elem is not None:
                    year = year_elem.text
                    month = month_elem.text.zfill(2) if month_elem is not None else "01"
                    day = day_elem.text.zfill(2) if day_elem is not None else "01"
                    dates[f"electronic_{date_type}"] = f"{year}-{month}-{day}"
            history_elem = pubmed_data.find(".//History")
            if history_elem is not None:
                for pub_date in history_elem.findall(".//PubMedPubDate[@PubStatus='epublish']"):
                    year_elem = pub_date.find(".//Year")
                    month_elem = pub_date.find(".//Month")
                    day_elem = pub_date.find(".//Day")
                    if year_elem is not None:
                        year = year_elem.text
                        month = month_elem.text.zfill(2) if month_elem is not None else "01"
                        day = day_elem.text.zfill(2) if day_elem is not None else "01"
                        dates["electronic_epublish"] = f"{year}-{month}-{day}"
        return dates
    
    def _extract_article_identifiers(self, article) -> Dict[str, str]:
        identifiers = {}
        for eloc_id in article.findall(".//ELocationID"):
            id_type = eloc_id.get("EIdType", "").lower()
            if eloc_id.text:
                identifiers[id_type] = eloc_id.text
        return identifiers
    
    def _extract_mesh_terms(self, medline) -> Dict[str, List[str]]:
        mesh_data = {"mesh_terms": [], "mesh_major": [], "mesh_minor": []}
        mesh_list = medline.find(".//MeshHeadingList")
        if mesh_list is not None:
            for mesh in mesh_list.findall(".//MeshHeading"):
                descriptor = mesh.find(".//DescriptorName")
                if descriptor is not None and descriptor.text:
                    term = descriptor.text
                    mesh_data["mesh_terms"].append(term)
                    is_major = descriptor.get("MajorTopicYN", "N") == "Y"
                    if is_major:
                        mesh_data["mesh_major"].append(term)
                    else:
                        mesh_data["mesh_minor"].append(term)
        return mesh_data
    
    def _extract_grants(self, medline) -> List[Dict[str, str]]:
        grants = []
        for grant in medline.findall(".//Grant"):
            grant_info = {}
            grant_id = grant.find(".//GrantID")
            agency = grant.find(".//Agency")
            country = grant.find(".//Country")
            if grant_id is not None:
                grant_info["grant_id"] = grant_id.text
            if agency is not None:
                grant_info["agency"] = agency.text
            if country is not None:
                grant_info["country"] = country.text
            if grant_info:
                grants.append(grant_info)
        return grants
    
    def _extract_chemicals(self, medline) -> List[Dict[str, str]]:
        chemicals = []
        for chemical in medline.findall(".//Chemical"):
            substance = chemical.find(".//NameOfSubstance")
            registry_number = chemical.find(".//RegistryNumber")
            if substance is not None and substance.text:
                chem_info = {"name": substance.text}
                if registry_number is not None and registry_number.text:
                    chem_info["registry_number"] = registry_number.text
                chemicals.append(chem_info)
        return chemicals
    
    def _extract_publication_history(self, pubmed_data) -> List[Dict[str, str]]:
        history = []
        if pubmed_data is not None:
            history_elem = pubmed_data.find(".//History")
            if history_elem is not None:
                for pub_date in history_elem.findall(".//PubMedPubDate"):
                    status = pub_date.get("PubStatus", "")
                    year_elem = pub_date.find(".//Year")
                    month_elem = pub_date.find(".//Month")
                    day_elem = pub_date.find(".//Day")
                    if year_elem is not None:
                        history.append({
                            "status": status, "year": year_elem.text,
                            "month": month_elem.text if month_elem is not None else "",
                            "day": day_elem.text if day_elem is not None else ""
                        })
        return history
    
    def _extract_references(self, pubmed_data) -> List[str]:
        references = []
        if pubmed_data is not None:
            ref_list = pubmed_data.find(".//ReferenceList")
            if ref_list is not None:
                for ref in ref_list.findall(".//Reference"):
                    citation = ref.find(".//Citation")
                    if citation is not None and citation.text:
                        references.append(citation.text)
        return references
    
    def _extract_comments_corrections(self, pubmed_data) -> List[Dict[str, str]]:
        comments = []
        if pubmed_data is not None:
            for comment in pubmed_data.findall(".//CommentsCorrections"):
                ref_type = comment.get("RefType", "")
                pmid_elem = comment.find(".//PMID")
                note_elem = comment.find(".//Note")
                if pmid_elem is not None:
                    comments.append({
                        "type": ref_type, "pmid": pmid_elem.text,
                        "note": note_elem.text if note_elem is not None else ""
                    })
        return comments
    
    async def fetch_details(self, pmid: str) -> Dict[str, Any]:
        results = await self._fetch_enhanced_batch([pmid])
        return results[0] if results else {}

    async def _enrich_with_pmc_fulltext(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich articles with PMC full text where available."""
        if not articles:
            return articles

        pmid_to_article = {a['pmid']: a for a in articles}
        pmids = list(pmid_to_article.keys())
        pmid_to_pmcid = {}

        for i in range(0, len(pmids), 200):
            batch = pmids[i:i+200]
            try:
                await self.rate_limiter.acquire()
                response = await self.client.get(
                    "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/",
                    params={
                        'ids': ','.join(batch), 'format': 'json',
                        'tool': 'medicuslabs', 'email': 'contact@medicuslabs.com'
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    for rec in data.get('records', []):
                        if rec.get('pmcid') and rec.get('pmid'):
                            pmid_to_pmcid[str(rec['pmid'])] = rec['pmcid']
            except Exception as e:
                logger.warning(f"PMC ID conversion failed for batch: {e}")

        if not pmid_to_pmcid:
            return articles

        pmids_no_abstract = [p for p in pmid_to_pmcid if not pmid_to_article[p].get('abstract')]
        pmids_with_abstract = [p for p in pmid_to_pmcid if pmid_to_article[p].get('abstract')]
        fetch_order = pmids_no_abstract + pmids_with_abstract
        fetched = 0
        max_fetch = 100

        for pmid in fetch_order[:max_fetch]:
            pmcid = pmid_to_pmcid[pmid]
            try:
                await self.rate_limiter.acquire()
                response = await self.client.get(
                    f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                    params={
                        'db': 'pmc', 'id': pmcid, 'rettype': 'xml',
                        **({"api_key": self.api_key} if self.api_key else {})
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    full_text = self._extract_pmc_text(response.text)
                    if full_text:
                        article = pmid_to_article[pmid]
                        article['pmc_full_text'] = full_text
                        article['pmcid'] = pmcid
                        if not article.get('abstract'):
                            article['abstract'] = full_text[:1000]
                        fetched += 1
            except Exception as e:
                logger.debug(f"Failed to fetch PMC full text for {pmcid}: {e}")

        logger.info(f"Enriched {fetched}/{len(fetch_order[:max_fetch])} articles with PMC full text")
        return articles

    def _extract_pmc_text(self, xml_text: str) -> Optional[str]:
        try:
            root = ET.fromstring(xml_text)
            body = root.find('.//body')
            if body is None:
                return None
            paragraphs = []
            for elem in body.iter():
                if elem.tag in ('p', 'title', 'label'):
                    text = ''.join(elem.itertext()).strip()
                    if text and len(text) > 10:
                        if elem.tag == 'title':
                            paragraphs.append(f"\n## {text}")
                        else:
                            paragraphs.append(text)
            full_text = '\n\n'.join(paragraphs)
            return full_text[:50000] if full_text else None
        except Exception as e:
            logger.debug(f"Error parsing PMC XML: {e}")
            return None

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        pmid = raw_data["pmid"]
        content_parts = []
        if raw_data.get("abstract"):
            content_parts.append(f"ABSTRACT: {raw_data['abstract']}")
        if raw_data.get("pmc_full_text"):
            content_parts.append(f"FULL TEXT:\n{raw_data['pmc_full_text']}")
        if raw_data.get("detailed_authors"):
            author_names = [author.get("name", "") for author in raw_data["detailed_authors"]]
            content_parts.append(f"AUTHORS: {', '.join(author_names[:10])}")
        if raw_data.get("mesh_terms"):
            content_parts.append(f"MESH TERMS: {', '.join(raw_data['mesh_terms'])}")
        if raw_data.get("keywords"):
            content_parts.append(f"KEYWORDS: {', '.join(raw_data['keywords'])}")
        if raw_data.get("chemicals"):
            chemical_names = [chem.get("name", "") for chem in raw_data["chemicals"]]
            content_parts.append(f"CHEMICALS: {', '.join(chemical_names)}")
        if raw_data.get("grants"):
            grant_agencies = [grant.get("agency", "") for grant in raw_data["grants"]]
            content_parts.append(f"FUNDING: {', '.join(grant_agencies)}")
        content = "\n\n".join(content_parts)
        summary = raw_data.get("abstract", "")[:500]
        
        pub_dates = raw_data.get("publication_dates", {})
        pub_date = ""
        for key in pub_dates:
            if key.startswith("electronic_") and pub_dates[key]:
                pub_date = pub_dates[key]
                break
        if not pub_date:
            pub_date = pub_dates.get("published", "")
        
        if pub_date:
            try:
                pub_datetime = datetime.strptime(pub_date, "%Y-%m-%d")
                if pub_datetime > datetime.now():
                    pub_history = raw_data.get("publication_history", [])
                    for hist in pub_history:
                        if hist.get("status") in ["pubmed", "entrez", "medline"]:
                            hist_date = f"{hist.get('year', '')}-{hist.get('month', '01').zfill(2)}-{hist.get('day', '01').zfill(2)}"
                            try:
                                hist_datetime = datetime.strptime(hist_date, "%Y-%m-%d")
                                if hist_datetime <= datetime.now():
                                    pub_date = hist_date
                                    break
                            except:
                                pass
            except:
                pass
        
        metadata = {
            "pmid": pmid, "pmcid": raw_data.get("pmcid", ""),
            "has_full_text": bool(raw_data.get("pmc_full_text")),
            "journal": raw_data.get("journal", ""), "issn": raw_data.get("issn", ""),
            "language": raw_data.get("language", "en"),
            "publication_date": pub_date, "publication_dates": pub_dates,
            "identifiers": raw_data.get("identifiers", {}),
            "authors": raw_data.get("authors", []),
            "detailed_authors": raw_data.get("detailed_authors", []),
            "mesh_terms": raw_data.get("mesh_terms", []),
            "mesh_major": raw_data.get("mesh_major", []),
            "mesh_minor": raw_data.get("mesh_minor", []),
            "suppl_mesh_terms": raw_data.get("suppl_mesh_terms", []),
            "keywords": raw_data.get("keywords", []),
            "article_types": raw_data.get("article_types", []),
            "grants": raw_data.get("grants", []),
            "chemicals": raw_data.get("chemicals", []),
            "publication_history": raw_data.get("publication_history", []),
            "references_cited": raw_data.get("references_cited", []),
            "comments_corrections": raw_data.get("comments_corrections", []),
            "abstract_structured": raw_data.get("abstract_structured", [])
        }
        
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        source_updated_at = None
        try:
            if pub_date:
                source_updated_at = datetime.strptime(pub_date, "%Y-%m-%d")
        except:
            pass
        
        last_revised = None
        pub_history = raw_data.get("publication_history", [])
        for hist in pub_history:
            if hist.get("status") == "revised":
                try:
                    year = hist.get('year', '')
                    month = hist.get('month', '01').zfill(2)
                    day = hist.get('day', '01').zfill(2)
                    if year:
                        revised_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                        if not last_revised or revised_date > last_revised:
                            last_revised = revised_date
                except:
                    pass
        
        if last_revised and source_updated_at and last_revised > source_updated_at:
            source_updated_at = last_revised
            metadata["last_revised_date"] = last_revised.strftime("%Y-%m-%d")
        
        return DocumentCreate(
            source_id=self.source_id, external_id=pmid, url=url,
            title=raw_data.get("title", ""), content=content,
            summary=summary, metadata=metadata
        ), source_updated_at
