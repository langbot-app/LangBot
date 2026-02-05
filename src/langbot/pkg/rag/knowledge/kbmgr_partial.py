
    async def get_all_knowledge_base_details(self) -> list[dict]:
        """Get all knowledge bases with enriched RAG engine details."""
        # 1. Get raw KBs from DB
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_rag.KnowledgeBase))
        knowledge_bases = result.all()

        # 2. Get all available RAG engines for enrichment
        engine_map = {}
        if self.ap.plugin_connector.is_enable_plugin:
            try:
                engines = await self.ap.plugin_connector.list_rag_engines()
                engine_map = {e["plugin_id"]: e for e in engines}
            except Exception as e:
                self.ap.logger.warning(f"Failed to list RAG engines: {e}")

        # 3. Serialize and enrich
        kb_list = []
        for kb in knowledge_bases:
            kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)
            self._enrich_kb_dict(kb_dict, engine_map)
            kb_list.append(kb_dict)

        return kb_list

    async def get_knowledge_base_details(self, kb_uuid: str) -> dict | None:
        """Get specific knowledge base with enriched RAG engine details."""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_rag.KnowledgeBase).where(persistence_rag.KnowledgeBase.uuid == kb_uuid)
        )
        kb = result.first()
        if not kb:
            return None

        kb_dict = self.ap.persistence_mgr.serialize_model(persistence_rag.KnowledgeBase, kb)
        
        # Fetch engines
        engine_map = {}
        if self.ap.plugin_connector.is_enable_plugin:
            try:
                engines = await self.ap.plugin_connector.list_rag_engines()
                engine_map = {e["plugin_id"]: e for e in engines}
            except Exception as e:
                self.ap.logger.warning(f"Failed to list RAG engines: {e}")

        self._enrich_kb_dict(kb_dict, engine_map)
        return kb_dict

    def _enrich_kb_dict(self, kb_dict: dict, engine_map: dict) -> None:
        """Helper to inject engine info into KB dict."""
        plugin_id = kb_dict.get("rag_engine_plugin_id")
        
        # Default fallback structure
        fallback_info = {
            "plugin_id": plugin_id,
            "name": plugin_id or "Internal (Legacy)",
            "capabilities": ["doc_ingestion"], 
        }

        if not plugin_id:
            kb_dict["rag_engine"] = fallback_info
            return

        engine_info = engine_map.get(plugin_id)
        if engine_info:
             kb_dict["rag_engine"] = {
                "plugin_id": plugin_id,
                "name": engine_info.get("name", plugin_id),
                "capabilities": engine_info.get("capabilities", []),
            }
        else:
             kb_dict["rag_engine"] = fallback_info
