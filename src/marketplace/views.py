from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from .forms import (ShoppingListForm, ShoppingListItemForm, PurchaseForm, 
                   PurchaseItemForm, ShoppingListApprovalForm, PurchaseStatusForm,
                   PurchaseItemSelectForm, MultiShopPurchaseForm)
from .models import ShoppingList, ShoppingListItem, Purchase, PurchaseItem, ShoppingListStatusHistory
from config.helpers import is_central_admin

def can_manage_purchases(user):
    """Check if user can manage purchases (central_admin, space_admin, institution_admin, or maintainer)"""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.user_type in ['central_admin', 'space_admin', 'institution_admin', 'maintainer']

def can_approve_purchases(user):
    """Check if user can approve purchases (central_admin, space_admin, or institution_admin)"""
    if not hasattr(user, 'profile'):
        return False
    return user.profile.user_type in ['central_admin', 'space_admin', 'institution_admin']

@login_required
@user_passes_test(can_manage_purchases)
def marketplace(request):
    """
    Marketplace view for managing purchases and shopping lists
    """
    org = getattr(request.user.profile, 'org', None)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    # Get shopping lists summary
    shopping_lists = ShoppingList.objects.filter(org=org) if org else ShoppingList.objects.none()
    
    # Get statistics
    total_lists = shopping_lists.count()
    pending_lists = shopping_lists.filter(status='pending').count()
    approved_lists = shopping_lists.filter(status='approved').count()
    completed_lists = shopping_lists.filter(status='completed').count()
    
    # Get recent purchases
    recent_purchases = Purchase.objects.filter(
        shopping_list__org=org
    ).order_by('-created_at')[:5] if org else []
    
    # Get total budget spent this month
    from datetime import datetime, timedelta
    current_month = datetime.now().replace(day=1)
    monthly_spending = Purchase.objects.filter(
        shopping_list__org=org,
        created_at__gte=current_month,
        status__in=['approved', 'ordered', 'received', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'org': org,
        'total_lists': total_lists,
        'pending_lists': pending_lists,
        'approved_lists': approved_lists,
        'completed_lists': completed_lists,
        'recent_purchases': recent_purchases,
        'monthly_spending': monthly_spending,
        'can_approve': can_approve_purchases(request.user),
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    
    return render(request, 'marketplace/marketplace.html', context)

# Shopping List Management Views
@login_required
@user_passes_test(can_manage_purchases)
def shopping_list_list(request):
    """List all shopping lists for the organization"""
    org = getattr(request.user.profile, 'org', None)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    shopping_lists = ShoppingList.objects.filter(org=org) if org else ShoppingList.objects.none()
    
    if status_filter:
        shopping_lists = shopping_lists.filter(status=status_filter)
    
    if search_query:
        shopping_lists = shopping_lists.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Annotate with item count and total cost
    shopping_lists = shopping_lists.annotate(
        item_count=Count('items'),
        estimated_total=Sum('items__estimated_cost')
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(shopping_lists, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'shopping_lists': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': ShoppingList.STATUS_CHOICES,
        'can_approve': can_approve_purchases(request.user),
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    
    return render(request, 'marketplace/shopping_list_list.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def create_shopping_list(request):
    """Create a new shopping list"""
    org = getattr(request.user.profile, 'org', None)
    if not org:
        messages.error(request, 'You must be associated with an organization to create shopping lists.')
        return redirect('marketplace:marketplace')
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    if request.method == 'POST':
        form = ShoppingListForm(request.POST)
        if form.is_valid():
            shopping_list = form.save(commit=False)
            shopping_list.created_by = request.user
            shopping_list.org = org
            shopping_list.save()
            messages.success(request, f'Shopping list "{shopping_list.name}" created successfully!')
            return redirect('marketplace:shopping_list_detail', slug=shopping_list.slug)
    else:
        form = ShoppingListForm()
    
    context = {
        'form': form,
        'org': org,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    return render(request, 'marketplace/create_shopping_list.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def shopping_list_detail(request, slug):
    """View details of a shopping list"""
    org = getattr(request.user.profile, 'org', None)
    shopping_list = get_object_or_404(ShoppingList, slug=slug, org=org)
    
    # Handle POST requests for status changes
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'submit_for_approval':
            if shopping_list.status in ['draft', 'rejected'] and shopping_list.items.exists():
                original_status = shopping_list.status
                
                # Only proceed if status will actually change
                if original_status != 'pending':
                    shopping_list.status = 'pending'
                    shopping_list.save()
                    
                    # Create status history entry
                    ShoppingListStatusHistory.objects.create(
                        shopping_list=shopping_list,
                        changed_by=request.user,
                        old_status=original_status,
                        new_status='pending',
                        comment=f'Submitted for approval from {original_status} status'
                    )
                    
                    if original_status == 'rejected':
                        messages.success(request, f'Shopping list "{shopping_list.name}" has been resubmitted for approval!')
                    else:
                        messages.success(request, f'Shopping list "{shopping_list.name}" has been submitted for approval!')
                else:
                    messages.info(request, 'Shopping list is already pending approval.')
                    
                return redirect('marketplace:shopping_list_detail', slug=slug)
            else:
                if not shopping_list.items.exists():
                    messages.error(request, 'Cannot submit an empty shopping list for approval. Please add items first.')
                else:
                    messages.error(request, 'Only draft or rejected shopping lists can be submitted for approval.')
    
    # Calculate totals
    items = shopping_list.items.all()
    estimated_total = sum(item.estimated_cost or 0 for item in items)
    
    # Calculate remaining items for purchase orders (for approved and purchase_created statuses)
    has_remaining_items = False
    if shopping_list.status in ['approved', 'purchase_created']:
        for item in items:
            # Calculate already ordered quantity
            ordered_quantity = PurchaseItem.objects.filter(
                shopping_list_item=item
            ).aggregate(total=Sum('quantity_ordered'))['total'] or 0
            
            # Check if there's remaining quantity
            remaining_quantity = item.quantity - ordered_quantity
            if remaining_quantity > 0:
                has_remaining_items = True
                break
    
    # Get status history
    status_history = shopping_list.status_history.all()
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    context = {
        'shopping_list': shopping_list,
        'items': items,
        'estimated_total': estimated_total,
        'status_history': status_history,
        'has_remaining_items': has_remaining_items,
        'can_approve': can_approve_purchases(request.user),
        'can_edit': (shopping_list.created_by == request.user or 
                    request.user.profile.user_type in ['central_admin', 'institution_admin']),
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    
    return render(request, 'marketplace/shopping_list_detail.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def add_shopping_list_item(request, slug):
    """Add item to shopping list"""
    org = getattr(request.user.profile, 'org', None)
    shopping_list = get_object_or_404(ShoppingList, slug=slug, org=org)
    
    # Check if user can edit this shopping list
    if (shopping_list.created_by != request.user and 
        request.user.profile.user_type not in ['central_admin', 'institution_admin']):
        messages.error(request, 'You do not have permission to edit this shopping list.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    if shopping_list.status not in ['draft', 'rejected']:
        messages.error(request, 'Cannot add items to a shopping list that is not in draft or rejected status.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    if request.method == 'POST':
        form = ShoppingListItemForm(request.POST, org=org)
        if form.is_valid():
            item = form.save(commit=False)
            item.shopping_list = shopping_list
            
            # Handle cost calculation properly
            unit_cost = form.cleaned_data.get('estimated_cost')
            quantity = form.cleaned_data.get('quantity', 1)
            
            if unit_cost is not None and quantity > 0:
                # If the user entered a unit cost, multiply by quantity
                item.estimated_cost = unit_cost * quantity
            
            item.save()
            messages.success(request, f'Item "{item.item_name}" added to shopping list!')
            return redirect('marketplace:shopping_list_detail', slug=slug)
    else:
        form = ShoppingListItemForm(org=org)
    
    context = {
        'form': form,
        'shopping_list': shopping_list,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    return render(request, 'marketplace/add_shopping_list_item.html', context)

@login_required
@user_passes_test(can_approve_purchases)
def approve_shopping_list(request, slug):
    """Approve or reject a shopping list"""
    org = getattr(request.user.profile, 'org', None)
    shopping_list = get_object_or_404(ShoppingList, slug=slug, org=org)
    
    if shopping_list.status != 'pending':
        messages.error(request, 'Only pending shopping lists can be approved or rejected.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    if request.method == 'POST':
        form = ShoppingListApprovalForm(request.POST, instance=shopping_list)
        if form.is_valid():
            old_status = shopping_list.status  # Capture before any changes
            new_status = form.cleaned_data['status']  # Get the new status from form
            
            shopping_list = form.save(commit=False)
            shopping_list.approved_by = request.user
            shopping_list.save()
            
            # Create status history entry only if status actually changed
            if old_status != new_status:
                ShoppingListStatusHistory.objects.create(
                    shopping_list=shopping_list,
                    changed_by=request.user,
                    old_status=old_status,
                    new_status=new_status,
                    comment=form.cleaned_data.get('approval_comment', '')
                )
            
            status_text = 'approved' if new_status == 'approved' else 'rejected'
            messages.success(request, f'Shopping list "{shopping_list.name}" has been {status_text}!')
            return redirect('marketplace:shopping_list_detail', slug=slug)
    else:
        form = ShoppingListApprovalForm(instance=shopping_list)
    
    # Get items and calculate totals
    items = shopping_list.items.all()
    estimated_total = sum(item.estimated_cost or 0 for item in items)
    
    # Calculate unit prices for display
    item_details = []
    for item in items:
        unit_price = "N/A"
        if item.estimated_cost and item.quantity > 0:
            unit_price = item.estimated_cost / item.quantity
            
        item_details.append({
            'item': item,
            'unit_price': unit_price
        })
    
    context = {
        'form': form,
        'shopping_list': shopping_list,
        'items': items,
        'item_details': item_details,
        'estimated_total': estimated_total,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    return render(request, 'marketplace/approve_shopping_list.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def create_purchase(request, slug):
    """Create a purchase order from approved shopping list (redirects to multi-shop purchase)"""
    # Redirect to the new multi-shop purchase view
    return redirect('marketplace:create_multi_shop_purchase', slug=slug)

@login_required
@user_passes_test(can_manage_purchases)
def purchase_detail(request, slug):
    """View purchase order details"""
    org = getattr(request.user.profile, 'org', None)
    purchase = get_object_or_404(Purchase, slug=slug, shopping_list__org=org)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    # Get all related purchase orders from the same shopping list
    related_purchases = Purchase.objects.filter(shopping_list=purchase.shopping_list).exclude(id=purchase.id)
    
    # Calculate remaining items to be purchased
    shopping_list_items = purchase.shopping_list.items.all()
    remaining_items = {}
    
    for item in shopping_list_items:
        purchased_quantity = PurchaseItem.objects.filter(
            shopping_list_item=item
        ).aggregate(total=Sum('quantity_ordered'))['total'] or 0
        
        remaining_items[item.id] = {
            'item': item,
            'total_quantity': item.quantity,
            'purchased_quantity': purchased_quantity,
            'remaining_quantity': item.quantity - purchased_quantity
        }
    
    context = {
        'purchase': purchase,
        'can_approve': can_approve_purchases(request.user),
        'related_purchases': related_purchases,
        'remaining_items': remaining_items,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    
    return render(request, 'marketplace/purchase_detail.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def edit_shopping_list_item(request, slug, item_slug):
    """Edit an existing shopping list item"""
    org = getattr(request.user.profile, 'org', None)
    shopping_list = get_object_or_404(ShoppingList, slug=slug, org=org)
    item = get_object_or_404(ShoppingListItem, slug=item_slug, shopping_list=shopping_list)
    
    # Check if user can edit this shopping list
    if (shopping_list.created_by != request.user and 
        request.user.profile.user_type not in ['central_admin', 'institution_admin']):
        messages.error(request, 'You do not have permission to edit this shopping list.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    if shopping_list.status not in ['draft', 'rejected']:
        messages.error(request, 'Cannot edit items in a shopping list that is not in draft or rejected status.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    if request.method == 'POST':
        form = ShoppingListItemForm(request.POST, instance=item, org=org)
        if form.is_valid():
            item = form.save(commit=False)
            
            # Handle cost calculation properly
            unit_cost = form.cleaned_data.get('estimated_cost')
            quantity = form.cleaned_data.get('quantity', 1)
            
            if unit_cost is not None and quantity > 0:
                # If the user entered a unit cost, multiply by quantity
                item.estimated_cost = unit_cost * quantity
                
            item.save()
            messages.success(request, f'Item "{item.item_name}" updated successfully!')
            return redirect('marketplace:shopping_list_detail', slug=slug)
    else:
        # For GET request, display the unit cost (estimated_cost / quantity)
        if item.estimated_cost and item.quantity > 0:
            unit_cost = item.estimated_cost / item.quantity
            item.estimated_cost = unit_cost  # Temporarily change to unit cost for the form
            form = ShoppingListItemForm(instance=item, org=org)
            # Reset back to total cost
            item.estimated_cost = unit_cost * item.quantity  # Reset to total cost
        else:
            form = ShoppingListItemForm(instance=item, org=org)
    
    context = {
        'form': form,
        'shopping_list': shopping_list,
        'item': item,
        'is_edit': True,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    return render(request, 'marketplace/edit_shopping_list_item.html', context)

@login_required
@user_passes_test(can_manage_purchases)
def create_multi_shop_purchase(request, slug):
    """Create a purchase order for selected items from the shopping list"""
    org = getattr(request.user.profile, 'org', None)
    shopping_list = get_object_or_404(ShoppingList, slug=slug, org=org)
    
    # Validate shopping list status
    if shopping_list.status != 'approved' and shopping_list.status != 'purchase_created':
        messages.error(request, 'Only approved shopping lists can be converted to purchase orders.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    # Get available items (those that haven't been fully purchased)
    available_items = []
    for item in shopping_list.items.all():
        # Calculate already ordered quantity
        ordered_quantity = PurchaseItem.objects.filter(
            shopping_list_item=item
        ).aggregate(total=Sum('quantity_ordered'))['total'] or 0
        
        # Add to available items if there's remaining quantity
        remaining_quantity = item.quantity - ordered_quantity
        if remaining_quantity > 0:
            item.available_quantity = remaining_quantity
            available_items.append(item)
    
    # Check if any items are available
    if not available_items:
        messages.info(request, 'All items in this shopping list have already been included in purchase orders.')
        return redirect('marketplace:shopping_list_detail', slug=slug)
    
    # Handle form submission
    if request.method == 'POST':
        return handle_purchase_creation(request, shopping_list, available_items)
    
    # Handle GET request - display form
    purchase_form = MultiShopPurchaseForm()
    item_form = PurchaseItemSelectForm(available_items)
    
    # Calculate estimated total for the shopping list
    estimated_total = sum(item.estimated_cost or 0 for item in shopping_list.items.all())
    
    context = {
        'purchase_form': purchase_form,
        'item_form': item_form,
        'shopping_list': shopping_list,
        'items': available_items,
        'estimated_total': estimated_total,
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    
    return render(request, 'marketplace/create_multi_shop_purchase.html', context)


def handle_purchase_creation(request, shopping_list, available_items):
    """Handle the POST request for creating a purchase order"""
    purchase_form = MultiShopPurchaseForm(request.POST)
    item_form = PurchaseItemSelectForm(available_items, request.POST)
    
    # Validate forms
    if not purchase_form.is_valid():
        messages.error(request, 'Please correct the errors in the supplier information.')
        return render_purchase_form_with_errors(request, shopping_list, available_items, purchase_form, item_form)
    
    # Process selected items
    selected_items = []
    errors = []
    
    for item in available_items:
        item_id = str(item.id)
        select_key = f'select_{item_id}'
        quantity_key = f'quantity_{item_id}'
        unit_cost_key = f'unit_cost_{item_id}'
        
        # Check if item is selected
        if request.POST.get(select_key):
            try:
                quantity = int(request.POST.get(quantity_key, 0))
                unit_cost = Decimal(request.POST.get(unit_cost_key, '0'))
                
                # Validate quantity
                if quantity <= 0:
                    errors.append(f'{item.item_name}: Quantity must be greater than 0')
                    continue
                
                if quantity > item.available_quantity:
                    errors.append(f'{item.item_name}: Quantity ({quantity}) exceeds available quantity ({item.available_quantity})')
                    continue
                
                # Validate unit cost
                if unit_cost <= 0:
                    errors.append(f'{item.item_name}: Unit cost must be greater than $0.00')
                    continue
                
                # Calculate totals
                item_total = quantity * unit_cost
                
                selected_items.append({
                    'item': item,
                    'quantity': quantity,
                    'unit_cost': unit_cost,
                    'total': item_total
                })
                
            except (ValueError, TypeError) as e:
                errors.append(f'{item.item_name}: Invalid quantity or unit cost entered')
    
    # Validate that items were selected
    if not selected_items:
        errors.append('Please select at least one item for the purchase order')
    
    # If there are errors, return to form
    if errors:
        for error in errors:
            messages.error(request, error)
        return render_purchase_form_with_errors(request, shopping_list, available_items, purchase_form, item_form)
    
    # Create the purchase order
    try:
        with transaction.atomic():
            purchase = create_purchase_order(request, purchase_form, shopping_list, selected_items)
            update_shopping_list_status(request, shopping_list, purchase)
            
            messages.success(request, f'Purchase order {purchase.purchase_id} created successfully with {len(selected_items)} items!')
            return redirect('marketplace:purchase_detail', slug=purchase.slug)
            
    except Exception as e:
        messages.error(request, f'An error occurred while creating the purchase order: {str(e)}')
        return render_purchase_form_with_errors(request, shopping_list, available_items, purchase_form, item_form)


def create_purchase_order(request, purchase_form, shopping_list, selected_items):
    """Create the purchase order and related items"""
    # Calculate total amount
    total_amount = sum(item['total'] for item in selected_items)
    
    # Create purchase order
    purchase = purchase_form.save(commit=False)
    purchase.shopping_list = shopping_list
    purchase.ordered_by = request.user
    purchase.status = 'pending'
    purchase.total_amount = total_amount
    purchase.save()
    
    # Create purchase items
    for selected in selected_items:
        PurchaseItem.objects.create(
            purchase=purchase,
            shopping_list_item=selected['item'],
            quantity_ordered=selected['quantity'],
            unit_cost=selected['unit_cost'],
            total_cost=selected['total']
        )
    
    return purchase


def update_shopping_list_status(request, shopping_list, purchase):
    """Update shopping list status if this is the first purchase"""
    # Check if this is the first purchase order created from this shopping list
    if not ShoppingListStatusHistory.objects.filter(
        shopping_list=shopping_list,
        new_status='purchase_created'
        ).exists():
        # Update status
        old_status = shopping_list.status
        shopping_list.status = 'purchase_created'
        shopping_list.save()
        
        # Create status history
        ShoppingListStatusHistory.objects.create(
            shopping_list=shopping_list,
            changed_by=request.user,
            old_status=old_status,
            new_status='purchase_created',
            comment=f'First purchase order {purchase.purchase_id} created'
        )


def render_purchase_form_with_errors(request, shopping_list, available_items, purchase_form, item_form):
    """Render the form with validation errors"""
    # Initialize space context variables
    selected_space = None
    space_settings = None
    user_spaces = None
    
    # Handle space context for different user types
    if (request.user.is_authenticated and hasattr(request.user, 'profile') and 
        request.user.profile.user_type == 'space_admin'):
        user_spaces = request.user.administered_spaces.all()
        selected_space = request.user.profile.current_active_space
        
        # If no active space is set or user can't access it, set to first available
        if not selected_space or not user_spaces.filter(id=selected_space.id).exists():
            if user_spaces.exists():
                selected_space = user_spaces.first()
                request.user.profile.switch_active_space(selected_space)
        
        if selected_space:
            space_settings = selected_space.settings
    elif (request.user.is_authenticated and hasattr(request.user, 'profile') and 
          request.user.profile.user_type == 'central_admin'):
        # For central admin, check if filtering by specific space
        space_filter = request.GET.get('space_filter')
        if space_filter and space_filter != 'no_space':
            try:
                from service_management.models import Spaces
                selected_space = Spaces.objects.get(slug=space_filter, org=request.user.profile.org)
            except Spaces.DoesNotExist:
                pass
    
    estimated_total = sum(item.estimated_cost or 0 for item in shopping_list.items.all())
    
    context = {
        'purchase_form': purchase_form,
        'item_form': item_form,
        'shopping_list': shopping_list,
        'items': available_items,
        'estimated_total': estimated_total,
        'form_errors': True,  # Flag to indicate there were errors
        # Add space context
        'selected_space': selected_space,
        'space_settings': space_settings,
        'user_spaces': user_spaces,
    }
    return render(request, 'marketplace/create_multi_shop_purchase.html', context)
