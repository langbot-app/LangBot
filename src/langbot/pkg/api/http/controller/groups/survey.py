import quart

from .. import group


@group.group_class('survey', '/api/v1/survey')
class SurveyRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/pending', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _get_pending() -> str:
            """Get pending survey for the frontend to display."""
            survey = self.ap.survey.get_pending_survey() if self.ap.survey else None
            return self.success(data={'survey': survey})

        @self.route('/respond', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _respond() -> str:
            """Submit survey response."""
            json_data = await quart.request.json
            survey_id = json_data.get('survey_id')
            answers = json_data.get('answers', {})
            completed = json_data.get('completed', True)

            if not survey_id:
                return self.fail(1, 'survey_id required')

            if self.ap.survey:
                ok = await self.ap.survey.submit_response(survey_id, answers, completed)
                if ok:
                    return self.success()
                return self.fail(2, 'Failed to submit response')
            return self.fail(3, 'Survey not available')

        @self.route('/dismiss', methods=['POST'], auth_type=group.AuthType.USER_TOKEN)
        async def _dismiss() -> str:
            """Dismiss survey."""
            json_data = await quart.request.json
            survey_id = json_data.get('survey_id')

            if not survey_id:
                return self.fail(1, 'survey_id required')

            if self.ap.survey:
                ok = await self.ap.survey.dismiss_survey(survey_id)
                if ok:
                    return self.success()
                return self.fail(2, 'Failed to dismiss')
            return self.fail(3, 'Survey not available')
