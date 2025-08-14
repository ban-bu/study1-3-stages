import streamlit as st
import pandas as pd
import os
import datetime

# 数据存储相关常量
DATA_FILE = "experiment_data.csv"

def initialize_experiment_data():
    """Initialize or load experiment data file"""
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=[
            'user_id', 'experiment_group', 'timestamp', 'design_duration', 
            'age', 'gender', 'shopping_frequency', 'purchase_intent', 
            'satisfaction_score', 'customize_difficulty',
            'price_willing_to_pay', 'theme', 'design_choice', 'uniqueness_importance',
            'ai_attitude', 'feedback'
        ])
        df.to_csv(DATA_FILE, index=False)
    return True

def save_experiment_data(data):
    """Save experiment data to CSV file"""
    try:
        df = pd.read_csv(DATA_FILE)
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# Survey page
def show_survey_page():
    st.title("👕 Clothing Customization Experiment Survey")
    st.markdown(f"### {st.session_state.experiment_group} - Your Feedback")
    
    if not st.session_state.submitted:
        st.markdown('<div class="purchase-intent">', unsafe_allow_html=True)
        
        # Calculate time spent on design
        design_duration = (datetime.datetime.now() - st.session_state.start_time).total_seconds() / 60
        
        # Purchase intention
        purchase_intent = st.slider(
            "If this T-shirt were sold in the market, how likely would you be to purchase it?",
            min_value=1, max_value=10, value=5,
            help="1 means definitely would not buy, 10 means definitely would buy"
        )
        
        # Satisfaction rating
        satisfaction_score = st.slider(
            "How satisfied are you with the final design result?",
            min_value=1, max_value=10, value=5,
            help="1 means very dissatisfied, 10 means very satisfied"
        )
        
        # Different questions for different groups
        if st.session_state.experiment_group == "AI Customization Group" or st.session_state.experiment_group == "AI Design Group" or st.session_state.experiment_group == "AI Creation Group":
            # AI customization group specific questions
            ai_effectiveness = st.slider(
                "How well does the AI-generated design meet your expectations?",
                min_value=1, max_value=10, value=5,
                help="1 means not at all, 10 means completely meets expectations"
            )
            
            ai_uniqueness = st.slider(
                "How unique do you think the AI-generated design is?",
                min_value=1, max_value=10, value=5,
                help="1 means not at all unique, 10 means very unique"
            )
            
            ai_experience = st.radio(
                "How does the AI customization experience compare to your previous shopping experiences?",
                options=["Better", "About the same", "Worse", "Cannot compare"]
            )
            
            ai_future = st.radio(
                "Would you consider using AI customization for clothing in the future?",
                options=["Definitely", "Probably", "Probably not", "Definitely not"]
            )
        else:
            # Preset design group specific questions
            design_variety = st.slider(
                "How satisfied are you with the variety of preset designs?",
                min_value=1, max_value=10, value=5,
                help="1 means very dissatisfied, 10 means very satisfied"
            )
            
            design_quality = st.slider(
                "How would you rate the quality of the selected design?",
                min_value=1, max_value=10, value=5,
                help="1 means very poor quality, 10 means excellent quality"
            )
            
            design_preference = st.radio(
                "Which type of clothing design do you prefer?",
                options=["Popular mainstream styles", "Rare unique designs", "Personalized custom designs", "Simple basic styles"]
            )
            
            design_limitation = st.radio(
                "Did you feel the preset designs limited your creative expression?",
                options=["Very limiting", "Somewhat limiting", "Barely limiting", "Not limiting at all"]
            )
        
        # Common questions for both groups
        customize_difficulty = st.slider(
            "How difficult was it to customize a T-shirt using this system?",
            min_value=1, max_value=10, value=5,
            help="1 means very difficult, 10 means very easy"
        )
        
        # Willing to pay price
        price_willing_to_pay = st.slider(
            "How much would you be willing to pay for this customized T-shirt (in USD)?",
            min_value=0, max_value=100, value=20, step=5
        )
        
        # Open-ended feedback
        feedback = st.text_area(
            "Please share any other feedback or suggestions about this customization experience",
            height=100
        )
        
        # Submit button
        if st.button("Submit Feedback"):
            # Collect all data
            experiment_data = {
                'user_id': st.session_state.user_id,
                'experiment_group': st.session_state.experiment_group,
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'design_duration': round(design_duration, 2),
                'age': st.session_state.user_info.get('age'),
                'gender': st.session_state.user_info.get('gender'),
                'shopping_frequency': st.session_state.user_info.get('shopping_frequency'),
                'purchase_intent': purchase_intent,
                'satisfaction_score': satisfaction_score,
                'customize_difficulty': customize_difficulty,
                'price_willing_to_pay': price_willing_to_pay,
                'theme': st.session_state.selected_preset if st.session_state.experiment_group == "Preset Design Group" else None,
                'design_choice': st.session_state.selected_preset if st.session_state.experiment_group == "Preset Design Group" else None,
                'uniqueness_importance': st.session_state.user_info.get('uniqueness_importance'),
                'ai_attitude': st.session_state.user_info.get('ai_attitude'),
                'feedback': feedback
            }
            
            # Add group-specific data
            if st.session_state.experiment_group == "AI Customization Group" or st.session_state.experiment_group == "AI Design Group" or st.session_state.experiment_group == "AI Creation Group":
                experiment_data.update({
                    'ai_effectiveness': ai_effectiveness,
                    'ai_uniqueness': ai_uniqueness,
                    'ai_experience': ai_experience,
                    'ai_future': ai_future
                })
            else:
                experiment_data.update({
                    'design_variety': design_variety,
                    'design_quality': design_quality,
                    'design_preference': design_preference,
                    'design_limitation': design_limitation
                })
            
            # Save data
            if save_experiment_data(experiment_data):
                st.session_state.submitted = True
                st.success("Thank you for your feedback! Your data has been recorded and will help our research.")
                st.rerun()
            else:
                st.error("Failed to save feedback data, please try again.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.success("You have successfully submitted the survey! Thank you for your participation.")
        
        if st.button("Return to Main Page"):
            # Reset session state, retain user ID and experiment data
            design_keys = [
                'base_image', 'current_image', 'current_box_position', 
                'generated_design', 'final_design', 'selected_preset',
                'page', 'experiment_group', 'submitted', 'start_time'
            ]
            for key in design_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Reinitialize necessary states
            st.session_state.page = "welcome"
            st.session_state.start_time = datetime.datetime.now()
            st.session_state.submitted = False
            st.rerun() 