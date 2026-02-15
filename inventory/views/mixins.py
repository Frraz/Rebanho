"""
Mixins reutilizáveis para views com filtros, busca e paginação.
"""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class FilterSearchPaginateMixin:
    """
    Mixin que adiciona filtro, busca e paginação a qualquer ListView.
    
    Uso:
        class MinhaListView(FilterSearchPaginateMixin, View):
            paginate_by = 20
            search_fields = ['name', 'description']
    """
    paginate_by = 20
    search_fields = []

    def apply_search(self, queryset, search_term):
        """Aplica busca textual em múltiplos campos."""
        if not search_term or not self.search_fields:
            return queryset
        from django.db.models import Q
        query = Q()
        for field in self.search_fields:
            query |= Q(**{f'{field}__icontains': search_term})
        return queryset.filter(query)

    def paginate_queryset(self, queryset, page):
        """Pagina o queryset."""
        paginator = Paginator(queryset, self.paginate_by)
        try:
            objects = paginator.page(page)
        except PageNotAnInteger:
            objects = paginator.page(1)
        except EmptyPage:
            objects = paginator.page(paginator.num_pages)
        return paginator, objects

    def get_filter_context(self, request, queryset):
        """
        Retorna contexto com busca, filtros e paginação aplicados.
        
        Retorna:
            dict com 'objects', 'paginator', 'page_obj', 'search_term'
        """
        search_term = request.GET.get('q', '').strip()
        page = request.GET.get('page', 1)

        queryset = self.apply_search(queryset, search_term)
        paginator, page_obj = self.paginate_queryset(queryset, page)

        return {
            'objects': page_obj,
            'paginator': paginator,
            'page_obj': page_obj,
            'search_term': search_term,
            'total_count': paginator.count,
        }