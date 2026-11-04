from core_agent.roles.alerts import ad_of


class TestAd:
    def test_reads_the_ad_name(self) -> None:
        """The mark the host puts on "Bellota" after the Tri VX ad (Sep 26, 2026)."""
        q = '[SYSTEM: The user replied to a Facebook ad: "VIDEO_MELON AND WATERMELON TRI HB (high CPR)"]\nBellota'
        assert ad_of(q) == "VIDEO_MELON AND WATERMELON TRI HB (high CPR)"

    def test_no_mark_means_no_ad(self) -> None:
        assert ad_of("do you sell chlorpyrifos?") == ""
