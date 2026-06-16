import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def send_ticket_confirmation(user_email, user_name, event_title, ticket_quantity, total_price):
    """
    Dispatches a confirmation email after a successful ticket purchase.
    """
    subject = f"Your Tickets for {event_title} are Confirmed!"
    
    # We construct a simple HTML email body
    html_message = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #ff6b00;">Ticket Confirmation</h2>
        <p>Hi {user_name},</p>
        <p>Thank you for your purchase! We are excited to confirm your tickets for <strong>{event_title}</strong>.</p>
        
        <div style="background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Order Details</h3>
            <p><strong>Event:</strong> {event_title}</p>
            <p><strong>Tickets:</strong> {ticket_quantity}</p>
            <p><strong>Total Paid:</strong> Kes {total_price}</p>
        </div>
        
        <p>You can view and download your tickets from your attendee dashboard.</p>
        
        <p>If you have any questions, feel free to reply to this email or contact us at <a href="mailto:support@eventhub.com">support@eventhub.com</a>.</p>
        <p>See you at the event!<br>- The EventHub Team</p>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Confirmation email successfully sent to {user_email} for event '{event_title}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email to {user_email}. Error: {str(e)}")
        return False

def send_newsletter_confirmation(user_email):
    """
    Dispatches a confirmation email after a successful newsletter subscription.
    """
    subject = "Welcome to EventHub!"
    
    html_message = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #ff6b00;">You're Subscribed!</h2>
        <p>Hi there,</p>
        <p>Thank you for subscribing to the EventHub newsletter. You will now receive the latest updates, exclusive event announcements, and special offers straight to your inbox.</p>
        
        <p>If you have any questions, feel free to reply to this email or contact us at <a href="mailto:support@eventhub.com">support@eventhub.com</a>.</p>
        <p>Stay tuned!<br>- The EventHub Team</p>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Newsletter confirmation email successfully sent to {user_email}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send newsletter confirmation email to {user_email}. Error: {str(e)}")
        return False


def send_organizer_event_crud_email(organizer_email, organizer_name, event_title, action, details):
    """
    Sends a confirmation email to the organizer when they create, edit, or delete an event.
    """
    action_colored = {
        'created': '#10b981', # green
        'edited': '#3b82f6', # blue
        'deleted': '#ef4444' # red
    }.get(action, '#ec6408')
    
    subject = f"Event Confirmation: '{event_title}' was successfully {action}!"
    
    html_message = f"""
    <html>
    <body style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="background: #ffffff; border-radius: 16px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
            <h2 style="color: {action_colored}; margin-top: 0; font-size: 24px; border-bottom: 2px solid #f1f5f9; padding-bottom: 15px;">
                Event {action.capitalize()} Successfully
            </h2>
            <p>Hi {organizer_name},</p>
            <p>This is a confirmation email to verify that your event <strong>"{event_title}"</strong> has been successfully <strong>{action}</strong> in your organizer portal.</p>
            
            <div style="background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin: 25px 0;">
                <h4 style="margin: 0 0 10px 0; color: #0f172a; font-size: 16px;">Details</h4>
                <p style="margin: 5px 0;"><strong>Event Title:</strong> {event_title}</p>
                {f'<p style="margin: 5px 0;"><strong>Date & Venue:</strong> {details}</p>' if details else ''}
            </div>
            
            <p>You can manage and monitor bookings for this event anytime through your organizer dashboard.</p>
            
            <p style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 30px; font-size: 13px; color: #64748b;">
                Thank you for choosing EventHub to coordinate your experiences.<br>
                Need assistance? Feel free to contact us at <a href="mailto:support@eventhub.com" style="color: #ec6408; text-decoration: none;">support@eventhub.com</a>.
            </p>
        </div>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[organizer_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Event CRUD email successfully sent to organizer {organizer_email} for event '{event_title}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to send Event CRUD email to {organizer_email}. Error: {str(e)}")
        return False


def send_admin_broadcast_email(recipient_email, subject, message, recipient_role):
    """
    Sends an email marketing campaign from the admin panel to users.
    """
    html_message = f"""
    <html>
    <body style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="background: #ffffff; border-radius: 16px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; border-top: 4px solid #ec6408;">
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="font-size: 24px; font-weight: 800; color: #ec6408; font-family: 'Outfit', sans-serif;">EventHub Spotlight</span>
            </div>
            
            <div style="color: #1e293b; font-size: 15px;">
                {message.replace('\n', '<br>')}
            </div>
            
            <p style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 30px; font-size: 12px; color: #94a3b8; text-align: center;">
                You received this as a registered {recipient_role} on EventHub.<br>
                <a href="/attendee/pages/privacy/" style="color: #ec6408; text-decoration: none;">Privacy Policy</a> | <a href="/support/" style="color: #ec6408; text-decoration: none;">Help Center</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast email to {recipient_email}. Error: {str(e)}")
        return False


def send_attendee_review_request_email(attendee_email, attendee_name, event_title, event_id):
    """
    Sends an event review request asking the attendee to rate the completed event on a scale of 1-5.
    """
    subject = f"How was '{event_title}'? Leave a quick review!"
    
    html_message = f"""
    <html>
    <body style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="background: #ffffff; border-radius: 16px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; border-top: 4px solid #ec6408;">
            <h2 style="color: #ec6408; margin-top: 0; font-size: 22px; text-align: center;">
                Share Your Experience!
            </h2>
            <p>Hi {attendee_name},</p>
            <p>We noticed that <strong>"{event_title}"</strong> has successfully concluded. We'd love to know what you thought of it!</p>
            <p>Your feedback is vital to help other attendees find the best experiences and to help organizers improve future events.</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <p style="font-weight: 600; margin-bottom: 15px; color: #0f172a;">Rate your overall experience:</p>
                <div style="display: inline-block; background: #f8fafc; padding: 12px 24px; border-radius: 50px; border: 1px solid #e2e8f0;">
                    <a href="/attendee/events/" style="font-size: 24px; text-decoration: none; color: #cbd5e1; margin: 0 4px;" title="1 Star">&#9733;</a>
                    <a href="/attendee/events/" style="font-size: 24px; text-decoration: none; color: #cbd5e1; margin: 0 4px;" title="2 Stars">&#9733;</a>
                    <a href="/attendee/events/" style="font-size: 24px; text-decoration: none; color: #cbd5e1; margin: 0 4px;" title="3 Stars">&#9733;</a>
                    <a href="/attendee/events/" style="font-size: 24px; text-decoration: none; color: #cbd5e1; margin: 0 4px;" title="4 Stars">&#9733;</a>
                    <a href="/attendee/events/" style="font-size: 24px; text-decoration: none; color: #cbd5e1; margin: 0 4px;" title="5 Stars">&#9733;</a>
                </div>
            </div>
            
            <p style="text-align: center; margin-top: 25px;">
                <a href="/attendee/dashboard/" style="background: #ec6408; color: #ffffff; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block; box-shadow: 0 4px 12px rgba(236,100,8,0.15);">
                    Write a Star Review
                </a>
            </p>
            
            <p style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 30px; font-size: 13px; color: #64748b; text-align: center;">
                Need assistance? Feel free to contact us at <a href="mailto:support@eventhub.com" style="color: #ec6408; text-decoration: none;">support@eventhub.com</a>.
            </p>
        </div>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[attendee_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send attendee review request email to {attendee_email}. Error: {str(e)}")
        return False


def send_organizer_performance_summary_email(organizer_email, organizer_name, event_title, total_attendees, total_revenue):
    """
    Sends a completed event performance summary report to the organizer.
    """
    subject = f"Performance Summary Report: '{event_title}' is completed!"
    
    html_message = f"""
    <html>
    <body style="font-family: 'Plus Jakarta Sans', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px; background: #f8fafc;">
        <div style="background: #ffffff; border-radius: 16px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; border-top: 4px solid #ec6408;">
            <h2 style="color: #ec6408; margin-top: 0; font-size: 24px; border-bottom: 2px solid #f1f5f9; padding-bottom: 15px;">
                Event Analytics Digest
            </h2>
            <p>Hi {organizer_name},</p>
            <p>Congratulations! Your event <strong>"{event_title}"</strong> has concluded. Here is your summarized metrics report:</p>
            
            <div style="background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin: 25px 0;">
                <h4 style="margin: 0 0 15px 0; color: #0f172a; font-size: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px;">Key Metrics</h4>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;"><strong>Total Seats Sold:</strong></td>
                        <td style="padding: 6px 0; text-align: right; font-weight: 600; color: #0f172a;">{total_attendees}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b;"><strong>Total Revenue Generated:</strong></td>
                        <td style="padding: 6px 0; text-align: right; font-weight: 600; color: #ec6408;">Kes {total_revenue:,.2f}</td>
                    </tr>
                </table>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <p style="font-weight: 600; margin-bottom: 12px; color: #0f172a;">Please rate the overall success of the event:</p>
                <div style="display: inline-block; background: #f8fafc; padding: 8px 18px; border-radius: 50px; border: 1px solid #e2e8f0;">
                    <a href="/organizer/dashboard/" style="font-size: 20px; text-decoration: none; color: #cbd5e1; margin: 0 2px;">&#9733;</a>
                    <a href="/organizer/dashboard/" style="font-size: 20px; text-decoration: none; color: #cbd5e1; margin: 0 2px;">&#9733;</a>
                    <a href="/organizer/dashboard/" style="font-size: 20px; text-decoration: none; color: #cbd5e1; margin: 0 2px;">&#9733;</a>
                    <a href="/organizer/dashboard/" style="font-size: 20px; text-decoration: none; color: #cbd5e1; margin: 0 2px;">&#9733;</a>
                    <a href="/organizer/dashboard/" style="font-size: 20px; text-decoration: none; color: #cbd5e1; margin: 0 2px;">&#9733;</a>
                </div>
            </div>

            <p style="border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 30px; font-size: 13px; color: #64748b;">
                Thank you for organizing outstanding events on EventHub.<br>
                Need help with payouts or analytics? Contact us at <a href="mailto:support@eventhub.com" style="color: #ec6408; text-decoration: none;">support@eventhub.com</a>.
            </p>
        </div>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[organizer_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send organizer performance summary email to {organizer_email}. Error: {str(e)}")
        return False

